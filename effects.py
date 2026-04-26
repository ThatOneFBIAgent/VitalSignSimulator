"""
CRT / visual post-processing effects for authentic monitor look.
- Scanlines
- Phosphor persistence (glow trail)
- Vignette
- Number glow / bloom
"""
import pygame
import numpy as np


class Effects:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.enabled = {
            "scanlines": True,
            "phosphor": True,
            "vignette": True,
            "glow": True,
        }

        # Pre-render scanline overlay
        self._scanline_surf = self._make_scanlines()
        # Pre-render vignette overlay
        self._vignette_surf = self._make_vignette()

    def _make_scanlines(self):
        surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for y in range(0, self.h, 3):
            pygame.draw.line(surf, (0, 0, 0, 50), (0, y), (self.w, y))
        return surf

    def _make_vignette(self):
        surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        # Radial gradient — darker at edges
        cx, cy = self.w // 2, self.h // 2
        max_r = (cx ** 2 + cy ** 2) ** 0.5
        for ring in range(0, int(max_r), 4):
            alpha = int(min(255, (ring / max_r) ** 2.5 * 120))
            if alpha < 2:
                continue
            pygame.draw.circle(surf, (0, 0, 0, alpha), (cx, cy), int(max_r) - ring, 4)
        return surf

    def apply_scanlines(self, screen):
        if self.enabled["scanlines"]:
            screen.blit(self._scanline_surf, (0, 0))

    def apply_vignette(self, screen):
        if self.enabled["vignette"]:
            screen.blit(self._vignette_surf, (0, 0))

    def render_glow_text(self, surface, font, text, color, pos):
        """Render text with a soft glow bloom behind it."""
        if self.enabled["glow"]:
            glow_surf = font.render(text, True, color)
            glow_surf.set_alpha(35)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx == 0 and dy == 0:
                        continue
                    surface.blit(glow_surf, (pos[0] + dx, pos[1] + dy))
        # Main text
        main = font.render(text, True, color)
        surface.blit(main, pos)

    def toggle(self, effect_name):
        if effect_name in self.enabled:
            self.enabled[effect_name] = not self.enabled[effect_name]
            return self.enabled[effect_name]
        return None
