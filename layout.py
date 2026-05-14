from __future__ import annotations

from math import ceil

from PIL import Image

try:
    from .models import RenderOptions
except ImportError:
    from models import RenderOptions


def compose_pages(panel_images: list[Image.Image], options: RenderOptions) -> list[Image.Image]:
    if options.layout_mode == "classic":
        return compose_classic_pages(panel_images, options)

    return compose_webtoon_pages(panel_images, options)


def compose_webtoon_pages(panel_images: list[Image.Image], options: RenderOptions) -> list[Image.Image]:
    if not panel_images:
        return []

    page_height = (options.padding * 2) + sum(panel.height for panel in panel_images)
    page_height += options.gutter * (len(panel_images) - 1)
    page = create_page_background(options.page_width, page_height, options)
    y = options.padding

    for panel in panel_images:
        page.paste(panel, (0, y))
        y += panel.height + options.gutter

    return [page]


def compose_classic_pages(panel_images: list[Image.Image], options: RenderOptions) -> list[Image.Image]:
    if not panel_images:
        return []

    panels_per_page = classic_panels_per_page(options)
    pages: list[Image.Image] = []

    for start in range(0, len(panel_images), panels_per_page):
        page_panels = panel_images[start : start + panels_per_page]
        pages.append(compose_classic_page(page_panels, options))

    return pages


def compose_classic_page(panel_images: list[Image.Image], options: RenderOptions) -> Image.Image:
    page = create_page_background(options.page_width, options.page_height, options)
    cell_width, cell_height = classic_panel_size(options)
    columns = classic_columns(options)

    for index, panel in enumerate(panel_images):
        row = index // columns
        column = index % columns
        x = options.padding + (column * (cell_width + options.gutter))
        y = options.padding + (row * (cell_height + options.gutter))
        if panel.size != (cell_width, cell_height):
            panel = panel.resize((cell_width, cell_height), Image.Resampling.LANCZOS)

        page.paste(panel, (x, y))

    return page


def classic_panel_size(options: RenderOptions) -> tuple[int, int]:
    columns = classic_columns(options)
    rows = classic_rows(options)
    cell_width = (options.page_width - (options.padding * 2) - (options.gutter * (columns - 1))) // columns
    cell_height = (options.page_height - (options.padding * 2) - (options.gutter * (rows - 1))) // rows

    return cell_width, cell_height


def classic_columns(options: RenderOptions) -> int:
    return 2 if classic_panels_per_page(options) > 1 else 1


def classic_rows(options: RenderOptions) -> int:
    return ceil(classic_panels_per_page(options) / classic_columns(options))


def classic_panels_per_page(options: RenderOptions) -> int:
    return max(2, min(options.classic_panels_per_page, 4))


def create_page_background(width: int, height: int, options: RenderOptions) -> Image.Image:
    color = (4, 8, 20) if options.theme_dark else (246, 241, 232)

    return Image.new("RGB", (width, height), color)

