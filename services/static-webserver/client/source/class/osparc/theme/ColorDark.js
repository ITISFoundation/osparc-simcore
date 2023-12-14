qx.Theme.define("osparc.theme.ColorDark", {
  include: osparc.theme.mixin.Color,

  colors: {
    "c00": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105),
    "c01": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 100),
    "c02": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 95),
    "c03": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 85),
    "c04": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 80),
    "c05": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 70),
    "c06": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 55),
    "c07": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 45),
    "c08": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 35),
    "c09": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 30),
    "c10": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 25),
    "c11": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 20),
    "c12": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 15),
    "c13": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 8),
    "c14": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 0),

    "strong-main": "rgba(0, 144, 208, 1)", // override in product
    "strong-text": "c12",
    "a-bit-transparent": "rgba(0, 0, 0, 0.4)",

    // main
    "background-main": "#222",
    "background-main-1": "c02",
    "background-main-2": "c03",
    "background-main-3": "c04",
    "background-main-4": "c05",
    "background-main-5": "c06",

    "background-card-overlay": "rgba(25, 33, 37, 0.8)",

    "primary-background-color": "rgba(0, 20, 46, 1)",
    "navigation_bar_background_color": "rgba(1, 18, 26, 0.8)",
    "modal-backdrop": "rgba(8, 9, 13, 1)",
    "fab_text": "contrasted-text-dark",
    "fab_background": "rgba(47, 50, 69, 1)",
    "input_background": "#213248",
    "window-popup-background": "rgba(66, 66, 66, 1)",
    "transparent_overlay": "rgba(1, 18, 26, 0.1)",

    "flash_message_bg": "input_background",

    // text
    "text": "rgba(216, 216, 216, 1)",
    "text-disabled": "rgba(113, 157, 181, 1)",
    "text-selected": "rgba(10, 182, 255, 1)",
    "text-placeholder": "rgba(174, 191, 207, 1)",
    "text-darker": "rgba(255, 255, 255, 1)",
    "contrasted-text-dark": "rgba(216, 216, 216, 1)",
    "contrasted-text-light": "rgba(255, 255, 255, 1)",
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
    "default-button-focus": "rgba(10, 182, 255, 0.5)",
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
    "material-button-background-hovered":  "default-button-hover",
    "material-button-background-pressed":  "default-button-active",
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
    "progressive-table-header": "lime",
    "progressive-table-row-background-even": "background-main",
    "progressive-table-row-background-odd": "background-main",
    "progressive-progressbar-background":  "background-main",
    "progressive-progressbar-indicator-done": "background-main",
    "progressive-progressbar-indicator-undone":  "background-main-1",
    "progressive-progressbar-percent-background":  "background-main",
    "progressive-progressbar-percent-text":  "background-main-1",



    // OSPARC
    "workbench-edge-comp-active": "#777777",
    "workbench-edge-api-active": "#BBBBBB",
    "workbench-start-hint": "#505050",

    "node-selected-background": "background-main-4",
    "node-title-text": "#DCDCDC",
    "node-port-text": "#BABABA",

    "logger-debug-message": "#FFFFFF",
    "logger-info-message": "#FFFFFF",

    "service-window-hint": "#808080",

    "progressbar": "#60909e",

    "loading-page-background-color": "#202020",
    "loading-page-text": "#FFFFFF",
    "loading-page-spinner": "#DDDDDD"
  }
});
