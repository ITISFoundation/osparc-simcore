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

    "background-card-overlay": "rgba(25, 33, 37, 0.8)",

    "primary-background-color": "rgba(0, 20, 46, 1)",
    "navigation_bar_background_color": "rgba(1, 18, 26, 0.8)",
    "modal-backdrop": "rgba(8, 9, 13, 1)",
    "fab_background": "rgba(47, 50, 69, 1)",
    "input_background": "rgba(46, 51, 55, 1)",
    "window-popup-background": "rgba(66, 66, 66, 1)",

    "flash_message_bg": "input_background",

    // text
    "text": "rgba(216, 216, 216, 1)",
    "text-disabled": "rgba(113, 157, 181, 1)",
    "text-selected": "rgba(10, 182, 255, 1)",
    "text-placeholder": "rgba(174, 191, 207, 1)",
    "text-darker": "rgba(255, 255, 255, 1)",
    "contrasted-text-dark": "rgba(255, 255, 255, 1)",
    "contrasted-text-light": "rgba(255, 255, 255, 1)",
    "link": "rgba(10, 182, 255, 1)",

    // shadows
    "bg-shadow": "c06",
    "shadow": qx.core.Environment.get("css.rgba") ? "a-bit-transparent" : "bg-shadow",

    // window
    "window-caption-background": "c01",
    "window-caption-background-active": "c04",
    "window-caption-text": "text",
    "window-caption-text-active": "c12",

    // material-button
    "material-button-background": "c04",
    "material-button-background-disabled": "c03",
    "material-button-background-hovered": "c05",
    "material-button-background-pressed": "c05",
    "material-button-text-disabled": "c07",
    "material-button-text": "text",

    // material-textfield
    "material-textfield": "c07",
    "material-textfield-focused": "text",
    "material-textfield-disabled": "c05",
    "material-textfield-invalid": "failed-red",
    "invalid": "failed-red",

    // backgrounds
    "background-selected": "c05",
    "background-selected-disabled": "c02",
    "background-selected-dark": "c04",
    "background-disabled": "c01",
    "background-disabled-checked": "c02",
    "background-pane": "c01",

    // tabview
    "tabview-unselected": "c14",
    "tabview-button-border": "c14",
    "tabview-label-active-disabled": "c10",
    "tabview-pane-background": "c01",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive": "c05",
    "scrollbar-active": "c06",

    // form
    "button": "c05",
    "button-border": "c06",
    "button-border-hovered": "c07",
    "button-box": "c04",
    "button-box-pressed": "c05",
    "border-lead": "c07",

    // window
    "window-border": "c03",
    "window-border-inner": "c02",

    // group box
    "white-box-border": "c03",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border": "c04",
    "border-focused": "c09",
    "border-invalid": "failed-red",
    "border-disabled": "c01",

    // separator
    "border-separator": "c07",

    // tooltip
    "tooltip": "c07",
    "tooltip-text": "c12",

    // table
    "table-header": "c01",
    "table-header-foreground": "c09",
    "table-header-border": "c07",
    "table-focus-indicator": "c06",

    // used in table code
    "table-header-cell": "c01",
    "table-row-background-focused-selected": "c05",
    "table-row-background-focused": "c04",
    "table-row-background-selected": "c05",
    "table-row-background-even": "c01",
    "table-row-background-odd": "c01",

    // foreground
    "table-row-selected": "c12",
    "table-row": "c09",

    // table grid color
    "table-row-line": "c01",
    "table-column-line": "c01",

    // used in progressive code
    "progressive-table-header": "c08",
    "progressive-table-row-background-even": "c01",
    "progressive-table-row-background-odd": "c01",
    "progressive-progressbar-background": "c00",
    "progressive-progressbar-indicator-done": "c01",
    "progressive-progressbar-indicator-undone": "c02",
    "progressive-progressbar-percent-background": "c00",
    "progressive-progressbar-percent-text": "c02",



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
