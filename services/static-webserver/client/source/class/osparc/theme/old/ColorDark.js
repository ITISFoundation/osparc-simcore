qx.Theme.define("osparc.theme.ColorDark", {
  // extend: osparc.theme.osparclight.Color,
  include: osparc.theme.mixin.Color,

  colors: {
    "c00": "#000000", // L=00
    "c01": "#202020", // L=13
    "c02": "#303030", // L=19
    "c03": "#404040", // L=25
    "c04": "#505050", // L=31
    "c05": "#606060", // L=38
    "c06": "#707070", // L=44
    "c07": "#808080", // L=50
    "c08": "#909090", // L=56
    "c09": "#A0A0A0", // L=63
    "c10": "#B0B0B0", // L=69
    "c11": "#C0C0C0", // L=75
    "c12": "#D0D0D0", // L=82
    "c13": "#EFEFEF", // L=88
    "c14": "#FFFFFF", // L=100

    "strong-main": "c06",
    "a-bit-transparent": "rgba(0, 0, 0, 0.4)",


    // main
    "background-main": "c01",
    "background-main-1": "c02",
    "background-main-2": "c03",
    "background-main-3": "c04",
    "background-main-4": "c05",
    "background-main-5": "c06",

    // text
    "text": "c12",
    "text-disabled": "c07",
    "text-selected": "c12",
    "text-placeholder": "c07",
    "text-darker": "c07",
    "contrasted-text-dark": "c01",
    "contrasted-text-light": "c12",
    "link": "c11",

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
    "table-header-foreground": "c11",
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
    "table-row": "text",

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
