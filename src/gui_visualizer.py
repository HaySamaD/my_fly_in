"""Interactive Pygame Graphical Interface for the Fly-in simulation.

Features dynamic hover inspection cards, compact zone occupancy indicators,
resolution-independent world space, and Excalidraw-style pan/zoom.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Sequence

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

from src.graph import Graph
from src.models import Zone, ZoneType
from src.router import ScheduledPlan
from src.simulator import Simulator


@dataclass(slots=True)
class DroneVisualState:
    """Tracks continuous spatial coordinates and visual state for a drone."""

    drone_id: int
    current_pos: tuple[float, float]
    target_pos: tuple[float, float]
    label: str
    rotation_angle: float = 0.0
    is_delivered: bool = False


class PygameVisualizer:
    """Interactive 2D graphical visualizer with dynamic hover cards."""

    COLOR_BG: tuple[int, int, int] = (13, 17, 23)
    COLOR_PANEL: tuple[int, int, int] = (22, 27, 34)
    COLOR_PANEL_BORDER: tuple[int, int, int] = (48, 54, 61)
    COLOR_EDGE: tuple[int, int, int] = (75, 85, 99)
    COLOR_TEXT: tuple[int, int, int] = (240, 246, 252)
    COLOR_TEXT_DIM: tuple[int, int, int] = (139, 148, 158)
    COLOR_ACCENT: tuple[int, int, int] = (88, 166, 255)
    COLOR_BADGE_BG: tuple[int, int, int] = (27, 32, 43)
    COLOR_MAP: dict[str, tuple[int, int, int]] = {
        "green": (46, 160, 67),
        "yellow": (219, 171, 9),
        "red": (248, 81, 73),
        "blue": (88, 166, 255),
        "purple": (163, 113, 247),
        "magenta": (219, 97, 162),
        "cyan": (56, 189, 248),
        "gray": (110, 118, 129),
        "grey": (110, 118, 129),
        "white": (240, 246, 252),
    }

    def __init__(
        self,
        graph: Graph,
        plans: Sequence[ScheduledPlan],
        width: int = 1280,
        height: int = 800,
        assets_dir: str | Path = "assets",
    ) -> None:
        """Initialize Pygame visualizer window and setup canvas.

        Args:
            graph: Simulation graph topology.
            plans: Pre-computed drone flight plans.
            width: Window width in pixels.
            height: Window height in pixels.
            assets_dir: Directory containing hub.png and drone.png.
        """
        if pygame is None:
            raise RuntimeError(
                "Pygame is not installed. Please run: pip install pygame"
            )
        pygame.init()
        pygame.display.set_caption(
            "Fly-in Multi-Drone Network Simulator"
        )
        self._graph = graph
        self._plans = plans
        self._width = width
        self._height = height
        self._is_fullscreen: bool = False
        self._screen = pygame.display.set_mode(
            (self._width, self._height), pygame.RESIZABLE
        )
        self._clock = pygame.time.Clock()

        # Cross-platform fonts
        self._font_title = pygame.font.SysFont(
            "DejaVu Sans, Arial", 16, bold=True
        )
        self._font_main = pygame.font.SysFont(
            "DejaVu Sans, Arial", 12, bold=True
        )
        self._font_small = pygame.font.SysFont("DejaVu Sans, Arial", 10)

        # Asset loading
        self._assets_dir = Path(assets_dir)
        self._hub_img = self._load_image("hub.png", (50, 50))
        self._drone_img = self._load_image("drone.png", (40, 40))

        # Normalized world topology
        self._world_positions: dict[str, tuple[float, float]] = {}
        self._span_x: float = 1.0
        self._span_y: float = 1.0
        self._compute_normalized_world()

        # Camera state (Pan & Zoom)
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._zoom: float = 1.0
        self._is_panning: bool = False
        self._pan_start: tuple[int, int] = (0, 0)

        # Simulation playback state
        self._simulator = Simulator(self._graph, self._plans)
        self._is_paused: bool = True
        self._is_visually_completed: bool = False
        self._speed_multiplier: float = 1.0
        self._turn_duration: float = 0.9
        self._turn_progress: float = 1.0

        # Drone runtime visual states
        self._drones_state: dict[int, DroneVisualState] = {}
        self._init_drone_states()
        self._update_drone_targets()

        # Hover state
        self._hovered_zone: Zone | None = None

    def _load_image(
        self, filename: str, target_size: tuple[int, int]
    ) -> pygame.Surface | None:
        """Safely load and rescale a transparent PNG asset."""
        filepath = self._assets_dir / filename
        if not filepath.is_file():
            return None
        try:
            surface = pygame.image.load(str(filepath)).convert_alpha()
            return pygame.transform.smoothscale(surface, target_size)
        except Exception:
            return None

    def _compute_normalized_world(self) -> None:
        """Compute normalized world coordinates centered at (0, 0)."""
        xs = [float(z.x) for z in self._graph.zones.values()]
        ys = [float(z.y) for z in self._graph.zones.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        self._span_x = max(max_x - min_x, 1.0)
        self._span_y = max(max_y - min_y, 1.0)
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0

        for zone in self._graph.zones.values():
            wx = zone.x - center_x
            wy = -(zone.y - center_y)
            self._world_positions[zone.name] = (wx, wy)

    def _get_base_scale(self) -> float:
        """Calculate dynamic scale factor based on window size."""
        usable_w = max(self._width - 320, 200)
        usable_h = max(self._height - 260, 200)
        return min(usable_w / self._span_x, usable_h / self._span_y)

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert immutable world coordinates to active screen pixels."""
        scale = self._get_base_scale() * self._zoom
        sx = wx * scale + self._pan_x * self._zoom + (self._width / 2.0)
        sy = wy * scale + self._pan_y * self._zoom + (self._height / 2.0)
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert screen pixel coordinates to immutable world coordinates."""
        scale = self._get_base_scale() * self._zoom
        wx = (sx - (self._width / 2.0) - self._pan_x * self._zoom) / scale
        wy = (sy - (self._height / 2.0) - self._pan_y * self._zoom) / scale
        return wx, wy

    def _init_drone_states(self) -> None:
        """Initialize continuous drone positions."""
        start_world_pos = self._world_positions[self._graph.start_zone.name]
        self._drones_state = {
            plan.drone_id: DroneVisualState(
                drone_id=plan.drone_id,
                current_pos=start_world_pos,
                target_pos=start_world_pos,
                label=f"D{plan.drone_id}",
            )
            for plan in self._plans
        }

    def _get_orbital_offset(
        self, index: int, total_in_zone: int
    ) -> tuple[float, float]:
        """Compute an orbital offset when multiple drones share a zone."""
        if total_in_zone <= 1:
            return (0.0, 0.0)
        base_scale = max(self._get_base_scale(), 1.0)
        radius_world = 32.0 / base_scale
        angle = (2.0 * math.pi * index) / total_in_zone
        return (radius_world * math.cos(angle), radius_world * math.sin(angle))

    def _update_drone_targets(self) -> None:
        """Recalculate destination target coordinates for all drones."""
        zone_occupants: dict[str, list[int]] = {
            z_name: [] for z_name in self._graph.zones
        }
        for d_id, drone in self._simulator._drones.items():
            if not drone.is_in_transit:
                zone_occupants[drone.current_zone].append(d_id)

        for zone_name, occupants in zone_occupants.items():
            base_pos = self._world_positions[zone_name]
            total = len(occupants)
            for idx, d_id in enumerate(occupants):
                offset = self._get_orbital_offset(idx, total)
                state = self._drones_state[d_id]
                state.target_pos = (
                    base_pos[0] + offset[0],
                    base_pos[1] + offset[1],
                )
                state.is_delivered = (
                    zone_name == self._graph.end_zone.name
                    and self._simulator._drones[d_id].is_delivered
                )

        # In-transit drones on restricted links
        for d_id, drone in self._simulator._drones.items():
            if drone.is_in_transit and drone.transit_target_zone:
                pos_a = self._world_positions[drone.current_zone]
                pos_b = self._world_positions[drone.transit_target_zone]
                state = self._drones_state[d_id]
                state.target_pos = (
                    (pos_a[0] + pos_b[0]) / 2.0,
                    (pos_a[1] + pos_b[1]) / 2.0,
                )
                state.is_delivered = False

        # Compute heading rotation angles
        for state in self._drones_state.values():
            dx = state.target_pos[0] - state.current_pos[0]
            dy = state.target_pos[1] - state.current_pos[1]
            if abs(dx) > 0.0001 or abs(dy) > 0.0001:
                state.rotation_angle = (
                    -math.degrees(math.atan2(dy, dx)) - 90.0
                )

    def _apply_turn_step(self) -> None:
        """Advance the simulation by one turn and trigger animation."""
        if self._simulator.is_completed:
            return
        for state in self._drones_state.values():
            state.current_pos = state.target_pos
        self._simulator.step()
        self._update_drone_targets()
        self._turn_progress = 0.0

    def _toggle_fullscreen(self) -> None:
        """Toggle between windowed and borderless fullscreen mode."""
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self._screen = pygame.display.set_mode(
                (1280, 800), pygame.RESIZABLE
            )
        self._width, self._height = self._screen.get_size()

    def run(self) -> None:
        """Start the Pygame main application loop."""
        running = True
        while running:
            dt = self._clock.tick(60) / 1000.0
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self._is_fullscreen:
                        self._width = event.w
                        self._height = event.h
                        self._screen = pygame.display.set_mode(
                            (self._width, self._height), pygame.RESIZABLE
                        )
                elif (event.type == pygame.KEYDOWN
                      and event.key == pygame.K_F11):
                    self._toggle_fullscreen()
                elif event.type == pygame.MOUSEWHEEL:
                    wx, wy = self.screen_to_world(float(mx), float(my))
                    zoom_factor = 1.15 if event.y > 0 else (1.0 / 1.15)
                    new_zoom = max(0.2, min(5.0, self._zoom * zoom_factor))
                    self._zoom = new_zoom
                    scale = self._get_base_scale() * self._zoom
                    self._pan_x = (
                        float(mx) - (self._width / 2.0) - wx * scale
                    ) / self._zoom
                    self._pan_y = (
                        float(my) - (self._height / 2.0) - wy * scale
                    ) / self._zoom
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mods = pygame.key.get_mods()
                    if event.button == 2 or (
                        event.button == 1 and bool(mods & pygame.KMOD_SHIFT)
                    ):
                        self._is_panning = True
                        self._pan_start = event.pos
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button in (1, 2):
                        self._is_panning = False
                elif event.type == pygame.MOUSEMOTION and self._is_panning:
                    dx = (event.pos[0] - self._pan_start[0]) / self._zoom
                    dy = (event.pos[1] - self._pan_start[1]) / self._zoom
                    self._pan_x += dx
                    self._pan_y += dy
                    self._pan_start = event.pos
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self._is_paused = not self._is_paused
                    elif event.key == pygame.K_RIGHT:
                        can_step = (
                            self._turn_progress >= 1.0
                            and not self._simulator.is_completed
                        )
                        if can_step:
                            self._apply_turn_step()
                    elif event.key == pygame.K_UP:
                        self._speed_multiplier = min(
                            self._speed_multiplier * 1.3, 5.0
                        )
                    elif event.key == pygame.K_DOWN:
                        self._speed_multiplier = max(
                            self._speed_multiplier / 1.3, 0.2
                        )
                    elif event.key == pygame.K_r:
                        self._simulator = Simulator(self._graph, self._plans)
                        self._init_drone_states()
                        self._update_drone_targets()
                        self._turn_progress = 1.0
                        self._is_visually_completed = False

            if self._turn_progress < 1.0:
                eff_dur = self._turn_duration / self._speed_multiplier
                self._turn_progress += dt / eff_dur
                if self._turn_progress >= 1.0:
                    self._turn_progress = 1.0
                    for state in self._drones_state.values():
                        state.current_pos = state.target_pos
                    if self._simulator.is_completed:
                        self._is_visually_completed = True
                    elif not self._is_paused:
                        self._apply_turn_step()
            elif not self._is_paused and not self._simulator.is_completed:
                self._apply_turn_step()

            self._render(mx, my)
            pygame.display.flip()

        pygame.quit()

    def _render(self, mouse_x: int, mouse_y: int) -> None:
        """Render all elements to the window buffer."""
        self._screen.fill(self.COLOR_BG)
        self._render_connections()
        self._render_zones(mouse_x, mouse_y)
        self._render_drones()
        self._render_hud()
        self._render_legend()
        if self._hovered_zone is not None:
            self._render_hover_card(self._hovered_zone, mouse_x, mouse_y)

    def _render_connections(self) -> None:
        """Draw connection links and capacities."""
        for conn in self._graph.connections:
            pos_a_world = self._world_positions[conn.zone_a]
            pos_b_world = self._world_positions[conn.zone_b]
            pos_a = self.world_to_screen(*pos_a_world)
            pos_b = self.world_to_screen(*pos_b_world)
            line_width = max(2, int(3 * self._zoom))
            pygame.draw.line(
                self._screen, self.COLOR_EDGE, pos_a, pos_b, width=line_width
            )
            if conn.max_link_capacity > 1:
                mid_x = (pos_a[0] + pos_b[0]) / 2.0
                mid_y = (pos_a[1] + pos_b[1]) / 2.0
                cap_txt = self._font_small.render(
                    f"link_cap:{conn.max_link_capacity}",
                    True,
                    self.COLOR_ACCENT,
                )
                self._screen.blit(
                    cap_txt, (mid_x - cap_txt.get_width() / 2.0, mid_y - 12.0)
                )

    def _render_zones(self, mouse_x: int, mouse_y: int) -> None:
        """Draw zone nodes, compact badges, and detect hover state."""
        self._hovered_zone = None
        for zone in self._graph.zones.values():
            pos_world = self._world_positions[zone.name]
            sx, sy = self.world_to_screen(*pos_world)
            zone_color = self._get_zone_color(zone)
            scaled_radius = int(28 * max(0.5, self._zoom))

            dist_to_mouse = math.hypot(mouse_x - sx, mouse_y - sy)
            if dist_to_mouse <= scaled_radius + 10:
                self._hovered_zone = zone

            ring_width = 4 if self._hovered_zone == zone else 3
            pygame.draw.circle(
                self._screen,
                zone_color,
                (int(sx), int(sy)),
                radius=scaled_radius,
                width=ring_width,
            )

            if self._hub_img is not None:
                img_size = int(48 * max(0.5, self._zoom))
                scaled_hub = pygame.transform.smoothscale(
                    self._hub_img, (img_size, img_size)
                )
                rect = scaled_hub.get_rect(center=(int(sx), int(sy)))
                self._screen.blit(scaled_hub, rect)
            else:
                pygame.draw.circle(
                    self._screen,
                    self.COLOR_PANEL,
                    (int(sx), int(sy)),
                    radius=scaled_radius - 3,
                )

            self._render_compact_badge(zone, sx, sy, scaled_radius)

    def _render_compact_badge(
        self, zone: Zone, sx: float, sy: float, radius: int
    ) -> None:
        """Render compact badge showing zone name and active drone count."""
        active_drones = [
            d.name
            for d in self._simulator._drones.values()
            if d.current_zone == zone.name
            and not d.is_in_transit
            and not (zone.is_end and d.is_delivered)
        ]
        if zone.is_start:
            count_str = f"{len(active_drones)}"
        elif zone.is_end:
            delivered_count = sum(
                1 for d in self._simulator._drones.values() if d.is_delivered
            )
            count_str = f"{delivered_count}"
        else:
            count_str = f"{len(active_drones)}/{zone.max_drones}"

        label_text = f"{zone.name} ({count_str})"
        text_surf = self._font_main.render(label_text, True, self.COLOR_TEXT)
        badge_w = text_surf.get_width() + 12
        badge_h = text_surf.get_height() + 4
        badge_x = int(sx - badge_w / 2.0)
        badge_y = int(sy + radius + 6.0)
        badge_rect = pygame.Rect(badge_x, badge_y, badge_w, badge_h)

        pygame.draw.rect(
            self._screen, self.COLOR_BADGE_BG, badge_rect, border_radius=4
        )
        pygame.draw.rect(
            self._screen,
            self.COLOR_PANEL_BORDER,
            badge_rect,
            width=1,
            border_radius=4,
        )
        self._screen.blit(text_surf, (badge_x + 6, badge_y + 2))

    def _render_hover_card(self, zone: Zone, mx: int, my: int) -> None:
        """Render rich floating diagnostic card on hover."""
        active_drones = [
            d.name
            for d in self._simulator._drones.values()
            if d.current_zone == zone.name
            and not d.is_in_transit
            and not (zone.is_end and d.is_delivered)
        ]
        if zone.is_start:
            cap_str = f"{len(active_drones)} active (infinite)"
        elif zone.is_end:
            delivered_count = sum(
                1 for d in self._simulator._drones.values() if d.is_delivered
            )
            cap_str = f"{delivered_count} delivered (infinite)"
        else:
            cap_str = f"{len(active_drones)} / {zone.max_drones}"

        drones_list_str = ", ".join(active_drones) if active_drones else "None"

        lines: list[tuple[str, str, tuple[int, int, int]]] = [
            (f"Zone: {zone.name}", "", self.COLOR_TEXT),
            ("Type:", zone.zone_type.value.upper(),
                self._get_zone_color(zone)),
            ("Coordinates:", f"({zone.x}, {zone.y})", self.COLOR_TEXT),
            ("Occupancy:", cap_str, self.COLOR_ACCENT),
            ("Drones inside:", drones_list_str, self.COLOR_TEXT),
        ]
        card_w = 230
        card_h = len(lines) * 18 + 16

        card_x = min(mx + 16, self._width - card_w - 12)
        card_y = min(my + 16, self._height - card_h - 12)
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

        pygame.draw.rect(
            self._screen, self.COLOR_PANEL, card_rect, border_radius=8
        )
        pygame.draw.rect(
            self._screen,
            self.COLOR_ACCENT,
            card_rect,
            width=1,
            border_radius=8,
        )

        for i, (label, val, val_color) in enumerate(lines):
            ly = card_y + 8 + i * 18
            lbl_surf = self._font_small.render(
                label, True, self.COLOR_TEXT_DIM
            )
            self._screen.blit(lbl_surf, (card_x + 10, ly))
            if val:
                val_surf = self._font_small.render(val, True, val_color)
                self._screen.blit(val_surf, (card_x + 95, ly))

    def _render_drones(self) -> None:
        """Draw smooth interpolated drone sprites with rotation."""
        t = min(max(self._turn_progress, 0.0), 1.0)
        t_smooth = t * t * (3.0 - 2.0 * t)
        for state in self._drones_state.values():
            curr_wx = (
                state.current_pos[0]
                + (state.target_pos[0] - state.current_pos[0]) * t_smooth
            )
            curr_wy = (
                state.current_pos[1]
                + (state.target_pos[1] - state.current_pos[1]) * t_smooth
            )
            sx, sy = self.world_to_screen(curr_wx, curr_wy)

            if self._drone_img is not None:
                drone_size = int(38 * max(0.5, self._zoom))
                scaled_drone = pygame.transform.smoothscale(
                    self._drone_img, (drone_size, drone_size)
                )
                rotated_drone = pygame.transform.rotate(
                    scaled_drone, state.rotation_angle
                )
                rect = rotated_drone.get_rect(center=(int(sx), int(sy)))
                self._screen.blit(rotated_drone, rect)
            else:
                pygame.draw.circle(
                    self._screen,
                    self.COLOR_ACCENT,
                    (int(sx), int(sy)),
                    radius=12,
                )

            id_txt = self._font_small.render(
                state.label, True, self.COLOR_TEXT)
            self._screen.blit(
                id_txt, (int(sx) - id_txt.get_width() / 2.0, int(sy) - 26.0)
            )

    def _render_hud(self) -> None:
        """Draw top metrics and status dashboard."""
        panel_rect = pygame.Rect(0, 0, self._width, 54)
        pygame.draw.rect(self._screen, self.COLOR_PANEL, panel_rect)
        pygame.draw.line(
            self._screen,
            self.COLOR_PANEL_BORDER,
            (0, 54),
            (self._width, 54),
            width=1,
        )

        delivered = sum(
            1 for d in self._simulator._drones.values() if d.is_delivered
        )
        status_str = (
            "PAUSED"
            if self._is_paused
            else ("FINISHED" if self._is_visually_completed else "FLYING")
        )

        hud_text = (
            f"Turn: {self._simulator.current_turn}       "
            f"Delivered: {delivered}/{self._simulator.total_drones}       "
            f"Speed: {self._speed_multiplier:.1f}x       "
            f"Status: {status_str}"
        )
        txt_surf = self._font_title.render(hud_text, True, self.COLOR_TEXT)
        self._screen.blit(txt_surf, (20, 16))

        controls_text = (
            "[F11] Fullscreen  [Space] Play/Pause  [Right] Step  "
            "[Scroll] Zoom  [Middle Drag] Pan  [R] Reset"
        )
        ctrl_surf = self._font_small.render(
            controls_text, True, self.COLOR_TEXT_DIM
        )
        self._screen.blit(
            ctrl_surf, (self._width - ctrl_surf.get_width() - 20, 20)
        )

    def _render_legend(self) -> None:
        """Draw zone classification legend at the bottom left."""
        legend_items = [
            ("Start Hub", self.COLOR_MAP["green"]),
            ("End Hub", self.COLOR_MAP["yellow"]),
            ("Priority (1t)", self.COLOR_MAP["green"]),
            ("Normal (1t)", self.COLOR_MAP["blue"]),
            ("Restricted (2t)", self.COLOR_MAP["red"]),
            ("Blocked", self.COLOR_MAP["gray"]),
        ]
        card_w = 140
        card_h = len(legend_items) * 20 + 28
        card_x = 20
        card_y = self._height - card_h - 20
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

        pygame.draw.rect(
            self._screen, self.COLOR_PANEL, card_rect, border_radius=8
        )
        pygame.draw.rect(
            self._screen,
            self.COLOR_PANEL_BORDER,
            card_rect,
            width=1,
            border_radius=8,
        )

        title = self._font_small.render(
            "ZONE TYPES", True, self.COLOR_TEXT_DIM
        )
        self._screen.blit(title, (card_x + 12, card_y + 8))

        for idx, (label, color) in enumerate(legend_items):
            ly = card_y + 26 + idx * 20
            pygame.draw.circle(
                self._screen, color, (card_x + 18, ly + 6), radius=5
            )
            lbl_surf = self._font_small.render(label, True, self.COLOR_TEXT)
            self._screen.blit(lbl_surf, (card_x + 30, ly))

    def _get_zone_color(self, zone: Zone) -> tuple[int, int, int]:
        """Return RGB color for a zone based on metadata or type."""
        if zone.color and zone.color.lower() in self.COLOR_MAP:
            return self.COLOR_MAP[zone.color.lower()]
        if zone.is_start:
            return self.COLOR_MAP["green"]
        if zone.is_end:
            return self.COLOR_MAP["yellow"]
        if zone.zone_type == ZoneType.PRIORITY:
            return self.COLOR_MAP["green"]
        if zone.zone_type == ZoneType.RESTRICTED:
            return self.COLOR_MAP["red"]
        if zone.zone_type == ZoneType.BLOCKED:
            return self.COLOR_MAP["gray"]
        return self.COLOR_MAP["blue"]
