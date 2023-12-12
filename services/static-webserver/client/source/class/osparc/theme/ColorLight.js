qx.Theme.define("osparc.theme.ColorLight", {
  include: osparc.theme.mixin.Color,

  colors: {
    "c00": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 0),
    "c01": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 8),
    "c02": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 15),
    "c03": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 25),
    "c04": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 35),
    "c05": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 45),
    "c06": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 55),
    "c07": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 60),
    "c08": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 65),
    "c09": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 70),
    "c10": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 80),
    "c11": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 85),
    "c12": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 95),
    "c13": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 100),
    "c14": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105),

    "strong-main": "rgba(0, 144, 208, 1)", // override in product
    "strong-text":  "background-main-1",
    "a-bit-transparent": "rgba(255, 255, 255, 0.4)",

    // main

    "background-main": "rgba(250,250,250, 1)", // Is manipulated
    "background-main-1": "c02",
    "background-main-2": "c03",
    "background-main-3": "c04",
    "background-main-4": "c05",
    "background-main-5": "c06",

    "background-card-overlay": "rgba(229, 229, 229, 0.8)",

    "primary-background-color": "rgba(255, 255, 255, 1)",
    "navigation_bar_background_color": "rgba(229, 229, 229, 0.8)",
    "modal-backdrop": "rgba(247, 248, 252, 0.4)",
    "fab_text": "contrasted-text-dark",
    "fab_background": "rgba(230, 235, 255, 1)",
    "input_background": "rgba(209, 214, 218, 1)",
    "window-popup-background": "rgba(255,255,255, 1)",
    "transparent_overlay": "rgba(1, 18, 26, 0.1)",

    "flash_message_bg": "input_background",

    // text
    "text": "rgba(40, 40, 40, 1)",
    "text-disabled": "rgba(113, 157, 181, 1)",
    "text-selected": "rgba(10, 182, 255, 1)",
    "text-placeholder": "rgba(90, 100, 110, 1)",
    "text-darker": "rgba(20, 20, 20, 1)",
    "contrasted-text-dark": "rgba(20, 20, 20, 1)",
    "contrasted-text-light": "rgba(40, 40, 40, 1)",
    "link": "rgba(10, 182, 255, 1)",

    // button
    "default-button-text": "contrasted-text-light",
    "default-button-text-outline": "contrasted-text-dark",
    "default-button-text-action": "contrasted-text-dark",
    "default-button-text-disabled": "text-disabled",
    "default-button": "rgba(10, 182, 255, 1)",
    "default-button-hover": "rgba(4, 73, 102, 1)",
    "default-button-hover-background": "rgba(4, 73, 102, 0.04)",
    "default-button-active": "rgba(9, 89, 122, 1)",
    "default-button-active-background": "rgba(4, 73, 102, 0.04)",
    "default-button-focus": "rgba(10, 182, 255, 1)",
    "default-button-focus-background": "rgba(4, 73, 102, 0.04)",
    "default-button-focus-blur": "rgba(254, 233, 86, 1)",

    // shadows
    "bg-shadow":  "background-main-5",
    "shadow": qx.core.Environment.get("css.rgba") ? "a-bit-transparent" : "bg-shadow",

    // window
    "window-caption-background": "background-main",
    "window-caption-background-active":  "background-main-3",
    "window-caption-text": "text",
    "window-caption-text-active": "c12",

    // material-button
    "material-button-background":  "fab_background",
    "material-button-background-disabled":  "transparent",
    "material-button-background-hovered":  "default-button-hover-background",
    "material-button-background-pressed":  "default-button-active-background",
    "material-button-text-disabled": "default-button-text-disabled",
    "material-button-text": "default-button-text",

    // material-textfield
    "material-textfield": "input_background",
    "material-textfield-focused": "success",
    "material-textfield-disabled": "default-button-text-disabled",
    "material-textfield-invalid": "error",
    "invalid": "error",

    // backgrounds
    "background-selected": "success_bg",
    "background-selected-disabled":  "default-button-text-disabled",
    "background-selected-dark":  "success_bg",
    "background-disabled": "background-main",
    "background-disabled-checked":  "background-main-1",
    "background-pane": "background-main",

    // tabview
    "tabview-unselected": "c14",
    "tabview-button-border": "c14",
    "tabview-label-active-disabled": "c10",
    "tabview-pane-background": "transparent",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive":  "background-main-4",
    "scrollbar-active":  "background-main-5",

    // form
    "button":  "background-main-4",
    "button-border":  "background-main-5",
    "button-border-hovered": "c07",
    "button-box":  "background-main-3",
    "button-box-pressed":  "background-main-4",
    "border-lead": "c07",

    // window
    "window-border":  "background-main-2",
    "window-border-inner":  "background-main-1",

    // group box
    "white-box-border":  "background-main-2",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border":  "background-main-3",
    "border-focused": "c09",
    "border-invalid": "failed-red",
    "border-disabled": "background-main",

    // separator
    "border-separator": "c07",

    // tooltip
    "tooltip": "flash_message_bg",
    "tooltip-text": "text",


    // table
    "table-header": "background-main",
    "table-header-foreground": "c09",
    "table-header-border": "c07",
    "table-focus-indicator":  "background-main-5",

    // used in table code
    "table-header-cell": "background-main",
    "table-row-background-focused-selected":  "background-main-4",
    "table-row-background-focused":  "background-main-3",
    "table-row-background-selected":  "background-main-4",
    "table-row-background-even": "background-main",
    "table-row-background-odd": "background-main",

    // foreground
    "table-row-selected": "c12",
    "table-row": "c09",

    // table grid color
    "table-row-line": "background-main",
    "table-column-line": "background-main",

    // used in progressive code
    "progressive-table-header": "c08",
    "progressive-table-row-background-even": "background-main",
    "progressive-table-row-background-odd": "background-main",
    "progressive-progressbar-background":  "background-main",
    "progressive-progressbar-indicator-done": "background-main",
    "progressive-progressbar-indicator-undone":  "background-main-1",
    "progressive-progressbar-percent-background":  "background-main",
    "progressive-progressbar-percent-text":  "background-main-1",



    // OSPARC
    "workbench-edge-comp-active": "#888888",
    "workbench-edge-api-active": "#444444",
    "workbench-start-hint": "#AFAFAF",

    "node-selected-background": "success_bg",
    "node-title-text": "#232323",
    "node-port-text": "#454545",

    "logger-debug-message": "#000000",
    "logger-info-message": "#000000",

    "service-window-hint": "#7F7F7F",

    "progressbar": "#9F6F61",

    "loading-page-background-color": "background-main",
    "loading-page-text": "#000000",
    "loading-page-spinner": "#222222"
  }
});
