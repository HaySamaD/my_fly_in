"""
Enterprise UI/UX Pygame visualizer for Fly-in drone simulation.

Features window resizing, smooth flight interpolation, glassmorphism HUD,
direct left-click dragging (pan), mouse-wheel zoom,
and clean responsive layout.
"""
from dataclasses import dataclass
import os
import sys
from typing import Dict, Tuple

import pygame

from src.core.enums import ActionType, DroneStatus, ZoneType
from src.core.models import Connection, Map, Zone
from src.simulation.engine import SimulationEngine


@dataclass
class Palette:
    """Modern Dark Cyberpunk UI Color Palette."""

    bg = (13, 16, 23)
    panel_bg = (22, 27, 38, 230)
    card_bg = (28, 34, 48, 220)

    # Zone Colors
    cls_normal = (52, 152, 219)
    cls_start = (46, 204, 113)
    cls_goal = (231, 76, 60)
    cls_restricted = (241, 196, 15)
    cls_priority = (155, 89, 182)
    cls_blocked = (108, 122, 137)

    # Connection and UI Accents
    conn_line = (60, 72, 92)
    border_accent = (52, 152, 219)

    btn_normal = (35, 43, 60)
    btn_hover = (52, 152, 219)

    text_light = (245, 247, 250)
    text_active = (241, 196, 15)
    text_muted = (150, 162, 180)


class SimpleButton:
    """Interactive button with hover detection and dynamic positioning."""

    def __init__(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        text: str,
        font: pygame.font.Font,
    ) -> None:
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font = font
        self.text_surf = font.render(text, True, (255, 255, 255))
        self.text_rect = self.text_surf.get_rect(center=self.rect.center)
        self.is_hovered = False

    def set_position(self, x: int, y: int) -> None:
        """Update button position dynamically when window resizes."""
        self.rect.x = x
        self.rect.y = y
        self.text_rect = self.text_surf.get_rect(center=self.rect.center)

    def check_hover(self, mouse_pos: Tuple[int, int]) -> bool:
        """Check if mouse position overlaps button area."""
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

    def draw(self, screen: pygame.Surface, palette: Palette) -> None:
        """Render button with hover glow."""
        color = palette.btn_hover if self.is_hovered else palette.btn_normal
        pygame.draw.rect(screen, color, self.rect, border_radius=10)
        border_col = (
            (255, 255, 255) if self.is_hovered else palette.conn_line
        )
        pygame.draw.rect(screen, border_col, self.rect, 2, border_radius=10)
        screen.blit(self.text_surf, self.text_rect)


def safe_load_image(
    filename: str, scale_w: int, scale_h: int
) -> pygame.Surface:
    """Load image from candidate asset directories with fallback graphics."""
    base_name = os.path.basename(filename)
    candidates = [
        filename,
        base_name,
        os.path.join("assets", base_name),
        os.path.join("src", "assets", base_name),
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                return pygame.transform.smoothscale(img, (scale_w, scale_h))
            except pygame.error:
                pass

    # Fallback surface if image asset fails to load
    surf = pygame.Surface((scale_w, scale_h), pygame.SRCALPHA)
    pygame.draw.rect(
        surf, (255, 255, 255), (0, 0, scale_w, scale_h), border_radius=8
    )
    pygame.draw.circle(
        surf, (52, 152, 219), (scale_w // 2, scale_h // 2), scale_w // 3
    )
    return surf


def get_tinted_surface(
    surface: pygame.Surface, color: Tuple[int, int, int]
) -> pygame.Surface:
    """Apply RGB color multiplication tint while preserving transparency."""
    tinted = surface.copy()
    tinted.fill(color + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted


def create_glow_surface(
    radius: int, color: Tuple[int, int, int, int]
) -> pygame.Surface:
    """Create radial alpha glow texture."""
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(color[3] * (r / radius) ** 2)
        pygame.draw.circle(surf, color[:3] + (alpha,), (radius, radius), r)
    return surf


class PygameVisualizer:
    """Interactive Enterprise Graphical Visualizer for Fly-in."""

    def __init__(
        self,
        map_obj: Map,
        engine: SimulationEngine,
        start_zone: Zone,
        goal_zone: Zone,
        width: int = 1280,
        height: int = 900,
    ) -> None:
        pygame.init()
        self.map = map_obj
        self.engine = engine
        self.start_zone = start_zone
        self.goal_zone = goal_zone
        self.width = width
        self.height = height

        # Enable RESIZABLE window flag
        self.screen = pygame.display.set_mode(
            (width, height), pygame.RESIZABLE
        )
        pygame.display.set_caption("Fly-in Fleet Command | 42 Project")
        self.clock = pygame.time.Clock()
        self.palette = Palette()

        # Fonts
        self.title_font = pygame.font.SysFont("Verdana", 20, bold=True)
        self.font = pygame.font.SysFont("Verdana", 12, bold=True)
        self.small_font = pygame.font.SysFont("Verdana", 10)
        self.btn_font = pygame.font.SysFont("Verdana", 13, bold=True)

        # Asset loading
        self.drone_base = safe_load_image(
            "drone.png", 32, 32
        )
        self.hub_base = safe_load_image("hub.png", 52, 52)

        self.glows: Dict[str, pygame.Surface] = {
            "start": create_glow_surface(36, self.palette.cls_start + (50,)),
            "goal": create_glow_surface(36, self.palette.cls_goal + (50,)),
            "prio": create_glow_surface(36, self.palette.cls_priority + (40,)),
        }

        # Zoom & Pan State
        self.zoom_level: float = 1.0
        self.pan_offset_x: float = 0.0
        self.pan_offset_y: float = 0.0
        self.is_panning: bool = False
        self.pan_start_pos: Tuple[int, int] = (0, 0)

        # Animation & Speed Control State
        self.auto_play: bool = False
        self.speed_multiplier: int = 1
        self.anim_progress: float = 1.0
        self.anim_speed_step: float = 0.05

        self.start_positions: Dict[str, Tuple[float, float]] = {}
        self.target_positions: Dict[str, Tuple[float, float]] = {}

        self._setup_coordinate_scaling()
        self._record_drone_positions(self.start_positions)
        self._record_drone_positions(self.target_positions)

        # Responsive Buttons Setup
        self.reset_button = SimpleButton(
            width - 150, 20, 130, 38, "RESET", self.btn_font
        )
        self.speed_button = SimpleButton(
            width - 150, 68, 130, 38, "Speed: 1x", self.btn_font
        )
        self.auto_button = SimpleButton(
            width - 150, 116, 130, 38, "AUTO >>", self.btn_font
        )

    def _update_button_positions(self) -> None:
        """Reposition interactive buttons relative to new window size."""
        self.reset_button.set_position(self.width - 150, 20)
        self.speed_button.set_position(self.width - 150, 68)
        self.auto_button.set_position(self.width - 150, 116)

    def _setup_coordinate_scaling(self) -> None:
        """Calculate graph bounding box bounds."""
        if self.map.zones:
            xs = [z.x for z in self.map.zones]
            ys = [z.y for z in self.map.zones]
            self.min_x, self.max_x = min(xs), max(xs)
            self.min_y, self.max_y = min(ys), max(ys)
        else:
            self.min_x = self.max_x = self.min_y = self.max_y = 0

    def _to_screen_pos(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert world coordinates into screen pixel space with zoom and pan.
        """
        margin_x, margin_y = 200, 220
        dx = self.max_x - self.min_x if self.max_x != self.min_x else 1
        dy = self.max_y - self.min_y if self.max_y != self.min_y else 1

        base_x = margin_x + (
            (x - self.min_x) / dx * (self.width - 2 * margin_x)
        )
        base_y = self.height - margin_y - (
            (y - self.min_y) / dy * (self.height - 2 * margin_y)
        )

        center_x, center_y = self.width / 2, self.height / 2
        zoomed_x = center_x + (base_x - center_x) * self.zoom_level
        zoomed_y = center_y + (base_y - center_y) * self.zoom_level

        final_x = int(zoomed_x + self.pan_offset_x)
        final_y = int(zoomed_y + self.pan_offset_y)
        return final_x, final_y

    def _record_drone_positions(
        self, pos_dict: Dict[str, Tuple[float, float]]
    ) -> None:
        """Snapshot drone locations for smooth linear interpolation flight."""
        for drone in self.map.drones:
            if drone.current_zone:
                pos_dict[drone.id] = (
                    float(drone.current_zone.x),
                    float(drone.current_zone.y),
                )
            else:
                for conn in self.map.connections:
                    if drone in conn.drones_on_link:
                        mid_x = (conn.from_zone.x + conn.to_zone.x) / 2.0
                        mid_y = (conn.from_zone.y + conn.to_zone.y) / 2.0
                        pos_dict[drone.id] = (mid_x, mid_y)
                        break

    def trigger_turn_step(
        self,
        drone_paths: Dict[
            str, Dict[int, Tuple[Zone | Connection, ActionType]]
        ],
    ) -> None:
        """Execute a single simulation step and initiate flight transition."""
        self._record_drone_positions(self.start_positions)
        self.engine.simulate_turn(drone_paths)
        self._record_drone_positions(self.target_positions)
        self.anim_progress = 0.0

    def _get_zone_visuals(
        self, zone: Zone
    ) -> Tuple[Tuple[int, int, int], str]:
        """Return RGB tint color and string label based on zone type."""
        if zone == self.start_zone:
            return self.palette.cls_start, "START HUB"
        elif zone == self.goal_zone:
            return self.palette.cls_goal, "GOAL HUB"
        elif zone.zone_type == ZoneType.BLOCKED:
            return self.palette.cls_blocked, "BLOCKED"
        elif zone.zone_type == ZoneType.RESTRICTED:
            return self.palette.cls_restricted, "RESTRICTED"
        elif zone.zone_type == ZoneType.PRIORITY:
            return self.palette.cls_priority, "PRIORITY"
        return self.palette.cls_normal, "NORMAL"

    def draw_connections(self) -> None:
        """Render connection edges between hubs."""
        for conn in self.map.connections:
            p1 = self._to_screen_pos(
                float(conn.from_zone.x), float(conn.from_zone.y)
            )
            p2 = self._to_screen_pos(
                float(conn.to_zone.x), float(conn.to_zone.y)
            )
            pygame.draw.line(self.screen, self.palette.conn_line, p1, p2, 4)

    def draw_zones(self) -> None:
        """Render zones, hubs, glows, and info panels."""
        for zone in self.map.zones:
            pos = self._to_screen_pos(float(zone.x), float(zone.y))
            color, type_label = self._get_zone_visuals(zone)

            if zone == self.start_zone:
                self.screen.blit(self.glows["start"], (pos[0]-36, pos[1]-36))
            elif zone == self.goal_zone:
                self.screen.blit(self.glows["goal"], (pos[0]-36, pos[1]-36))
            elif zone.zone_type == ZoneType.PRIORITY:
                self.screen.blit(self.glows["prio"], (pos[0]-36, pos[1]-36))

            tinted_hub = get_tinted_surface(self.hub_base, color)
            self.screen.blit(tinted_hub, (pos[0] - 26, pos[1] - 26))

            panel_y = pos[1] + 32
            name_lbl = self.font.render(zone.name, True, (255, 255, 255))
            type_txt = self.small_font.render(type_label, True, color)

            drones_in_zone = zone.drones_present
            cap_str = f"Drones: {len(drones_in_zone)}/{zone.max_drones}"
            d_color = (
                self.palette.text_active if drones_in_zone
                else self.palette.text_muted
            )
            cap_txt = self.small_font.render(cap_str, True, d_color)

            card_w = max(name_lbl.get_width(), 90) + 16
            card_h = 52
            card_rect = pygame.Rect(
                pos[0] - card_w // 2, panel_y, card_w, card_h
            )
            pygame.draw.rect(
                self.screen, self.palette.card_bg, card_rect, border_radius=6
            )
            pygame.draw.rect(
                self.screen,
                self.palette.conn_line, card_rect, 1, border_radius=6
            )

            self.screen.blit(
                name_lbl, (pos[0] - name_lbl.get_width() // 2, panel_y + 4)
            )
            self.screen.blit(
                type_txt, (pos[0] - type_txt.get_width() // 2, panel_y + 20)
            )
            self.screen.blit(
                cap_txt, (pos[0] - cap_txt.get_width() // 2, panel_y + 35)
            )

    def draw_drones(self) -> None:
        """Render interpolated active drone movement transitions."""
        for drone in self.map.drones:
            s_pos = self.start_positions.get(drone.id, (0.0, 0.0))
            t_pos = self.target_positions.get(drone.id, s_pos)

            curr_x = s_pos[0] + (t_pos[0] - s_pos[0]) * self.anim_progress
            curr_y = s_pos[1] + (t_pos[1] - s_pos[1]) * self.anim_progress

            scr_pos = self._to_screen_pos(curr_x, curr_y)
            self.screen.blit(
                self.drone_base, (scr_pos[0] - 16, scr_pos[1] - 38)
            )

            tag = self.small_font.render(
                drone.id, True, self.palette.text_active
            )
            self.screen.blit(tag, (scr_pos[0] - 6, scr_pos[1] - 50))

    def draw_hud(self) -> None:
        """Render Glassmorphism HUD overlay and control buttons."""
        hud_rect = pygame.Rect(15, 15, 360, 140)
        pygame.draw.rect(
            self.screen, self.palette.panel_bg, hud_rect, border_radius=12
        )
        pygame.draw.rect(
            self.screen,
            self.palette.border_accent,
            hud_rect,
            2,
            border_radius=12,
        )

        title = self.title_font.render(
            "FLEET COMMAND", True, self.palette.text_active
        )
        self.screen.blit(title, (25, 22))

        turn_txt = self.font.render(
            f"Turn Step: {self.engine.current_turn}",
            True,
            self.palette.text_light,
        )
        self.screen.blit(turn_txt, (25, 54))

        finished_cnt = sum(
            1 for d in self.map.drones if d.status == DroneStatus.ARRIVED
        )
        drone_txt = self.font.render(
            f"Arrived at Goal: {finished_cnt}/{len(self.map.drones)}",
            True,
            self.palette.text_light,
        )
        self.screen.blit(drone_txt, (25, 76))

        ctrl_txt1 = self.small_font.render(
            "Left Drag: Pan Canvas | Wheel: Zoom",
            True,
            self.palette.text_muted,
        )
        self.screen.blit(ctrl_txt1, (25, 102))

        ctrl_txt2 = self.small_font.render(
            "Press [SPACE] or AUTO for smooth flight",
            True,
            self.palette.text_muted,
        )
        self.screen.blit(ctrl_txt2, (25, 118))

        # Render Interactive Buttons
        self.reset_button.draw(self.screen, self.palette)
        self.speed_button.draw(self.screen, self.palette)
        self.auto_button.draw(self.screen, self.palette)

    def draw_frame(self) -> None:
        """Render complete visualizer frame."""
        self.screen.fill(self.palette.bg)
        self.draw_connections()
        self.draw_zones()
        self.draw_drones()
        self.draw_hud()
        pygame.display.flip()

    def run(
        self,
        drone_paths: Dict[
            str, Dict[int, Tuple[Zone | Connection, ActionType]]
        ],
    ) -> bool:
        """Main application interactive execution loop."""
        running = True
        reset_requested = False

        while running:
            mouse_pos = pygame.mouse.get_pos()

            if self.anim_progress < 1.0:
                self.anim_progress = min(
                    1.0, self.anim_progress + self.anim_speed_step
                )

            if (
                self.auto_play
                and not self.engine.is_finished()
                and self.anim_progress >= 1.0
            ):
                self.trigger_turn_step(drone_paths)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    sys.exit(0)

                # Responsive Window Resizing
                elif event.type == pygame.VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    self.screen = pygame.display.set_mode(
                        (self.width, self.height), pygame.RESIZABLE
                    )
                    self._update_button_positions()

                elif event.type == pygame.MOUSEMOTION:
                    self.reset_button.check_hover(mouse_pos)
                    self.speed_button.check_hover(mouse_pos)
                    self.auto_button.check_hover(mouse_pos)

                    if self.is_panning:
                        self.pan_offset_x += (
                            mouse_pos[0] - self.pan_start_pos[0]
                        )
                        self.pan_offset_y += (
                            mouse_pos[1] - self.pan_start_pos[1]
                        )
                        self.pan_start_pos = mouse_pos

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4:
                        self.zoom_level = min(3.0, self.zoom_level + 0.1)
                    elif event.button == 5:
                        self.zoom_level = max(0.4, self.zoom_level - 0.1)

                    elif event.button == 1:
                        if self.reset_button.is_hovered:
                            reset_requested = True
                            running = False
                        elif self.speed_button.is_hovered:
                            speeds = [1, 2, 4]
                            curr_idx = speeds.index(self.speed_multiplier)
                            self.speed_multiplier = speeds[
                                (curr_idx + 1) % len(speeds)
                            ]
                            self.anim_speed_step = (
                                0.04 * self.speed_multiplier
                            )
                            self.speed_button = SimpleButton(
                                self.width - 150,
                                68,
                                130,
                                38,
                                f"Speed: {self.speed_multiplier}x",
                                self.btn_font,
                            )
                        elif self.auto_button.is_hovered:
                            self.auto_play = not self.auto_play
                            label = "PAUSE" if self.auto_play else "AUTO >>"
                            self.auto_button = SimpleButton(
                                self.width - 150,
                                116,
                                130,
                                38,
                                label,
                                self.btn_font,
                            )
                        else:
                            self.is_panning = True
                            self.pan_start_pos = mouse_pos

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.is_panning = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        sys.exit(0)
                    elif (
                        event.key == pygame.K_SPACE
                        and self.anim_progress >= 1.0
                        and not self.engine.is_finished()
                    ):
                        self.trigger_turn_step(drone_paths)

            self.draw_frame()
            self.clock.tick(60)

        return reset_requested
