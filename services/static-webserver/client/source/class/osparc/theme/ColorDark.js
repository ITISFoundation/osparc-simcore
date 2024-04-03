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

    "product-color": "rgba(0, 144, 208, 1)", // override in product
    "strong-main": "product-color",
    "strong-text": "rgba(255, 255, 255, 1)",
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
    "tab_navigation_bar_background_color": "c00",
    "modal-backdrop": "rgba(8, 9, 13, 1)",
    "fab_text": "contrasted-text-dark",
    "fab-background": "rgba(255, 255, 255, 0.2)",
    "input_background": "#213248",
    "input_background_disable": "rgba(113, 157, 181, 0.25)",
    "window-popup-background": "rgba(66, 66, 66, 1)",
    "transparent_overlay": "rgba(1, 18, 26, 0.1)",

    "flash_message_bg": "input_background",

    // text
    "text": "rgba(216, 216, 216, 1)",
    "text-disabled": "rgba(113, 157, 181, 1)",
    "text-selected": "rgba(255, 255, 255, 1)",
    "text-placeholder": "rgba(174, 191, 207, 1)",
    "text-darker": "rgba(255, 255, 255, 1)",
    "contrasted-text-dark": "rgba(216, 216, 216, 1)",
    "contrasted-text-light": "rgba(255, 255, 255, 1)",
    "link": "rgba(10, 182, 255, 1)",

    // shadows
    "bg-shadow":  "background-main-5",
    "box-shadow":  "rgba(0,0,0, 0.15)",
    "shadow": qx.core.Environment.get("css.rgba") ? "a-bit-transparent" : "bg-shadow",

    // window
    "window-caption-background": "background-main",
    "window-caption-background-active":  "background-main-3",
    "window-caption-text": "text",
    "window-caption-text-active": "c12",

    // material-button
    "material-button-background": "fab-background",
    "material-button-background-disabled": "default-button-disabled-background",
    "material-button-background-hovered": "default-button-hover-background",
    "material-button-background-pressed": "default-button-active-background",
    "material-button-text-disabled": "default-button-disabled-background",
    "material-button-text": "default-button-text-outline",

    // material-textfield
    "material-textfield": "input_background",
    "material-textfield-focused": "product-color",
    "material-textfield-disabled": "default-button-disabled",
    "material-textfield-invalid": "error",
    "invalid": "error",

    // backgrounds
    "background-selected": "default-button-background",
    "background-selected-disabled":  "default-button-disabled",
    "background-selected-dark":  "product-color",
    "background-disabled": "background-main",
    "background-disabled-checked":  "background-main-1",
    "background-pane": "background-main",

    // tabview
    "tabview-unselected": "c14",
    "tabview-button-border": "product-color",
    "tabview-label-active-disabled": "c10",
    "tabview-pane-background": "transparent",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive":  "background-main-4",
    "scrollbar-active":  "background-main-5",

    // form
    "button": "background-main-4",
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
    "border-separator": "fab-background",

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
    "workbench-edge-comp-active": "#777777",
    "workbench-edge-api-active": "#BBBBBB",
    "workbench-start-hint": "#505050",

    "node-background": "rgba(113, 157, 181, 0.5)",
    "node-selected-background": "background-selected",
    "node-title-text": "text-selected",
    "node-port-text": "#454545",

    "logger-debug-message": "#FFFFFF",
    "logger-info-message": "#FFFFFF",

    "service-window-hint": "#808080",

    "progressbar": "success",
    "progressbar-disabled": "rgba(113, 157, 181, 0.25)",
    "progressbar-runner": "rgba(228, 234, 237, 0.5)",

    "loading-page-background-color": "#202020",
    "loading-page-text": "#FFFFFF",
    "loading-page-spinner": "#DDDDDD"
  }
});
