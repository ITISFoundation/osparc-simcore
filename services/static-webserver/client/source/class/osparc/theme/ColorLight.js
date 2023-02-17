qx.Theme.define("osparc.theme.ColorLight", {
  // extend: osparc.theme.osparclight.Color,
  include: osparc.theme.mixin.Color,

  colors: {
    "c00": "#FFFFFF", // L=100
    "c01": "#EFEFEF", // L=94
    "c02": "#C0C0C0", // L=75
    "c03": "#B0B0B0", // L=69
    "c04": "#A0A0A0", // L=63
    "c05": "#909090", // L=56
    "c06": "#808080", // L=50
    "c07": "#707070", // L=44
    "c08": "#606060", // L=38
    "c09": "#505050", // L=31
    "c10": "#404040", // L=25
    "c11": "#303030", // L=19
    "c12": "#202020", // L=13
    "c13": "#101010", // L=06
    "c14": "#000000", // L=00

    "strong-main": "c06",
    "a-bit-transparent": "rgba(255, 255, 255, 0.4)",


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
    "material-button-background": "c03",
    "material-button-background-disabled": "c02",
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
    "window-border": "c04",
    "window-border-inner": "c01",

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
    "workbench-edge-comp-active": "#888888",
    "workbench-edge-api-active": "#444444",
    "workbench-start-hint": "#AFAFAF",

    "node-selected-background": "background-main-4",
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
