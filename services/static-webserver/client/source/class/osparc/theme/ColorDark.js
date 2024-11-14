qx.Theme.define("osparc.theme.ColorDark", {
  include: osparc.theme.mixin.Color,

  colors: {
    // 105-0
    "c00": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105),
    "c01": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-5),
    "c02": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-10),
    "c03": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-20),
    "c04": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-25),
    "c05": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-35),
    "c06": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-50),
    "c07": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-60),
    "c08": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-70),
    "c09": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-75),
    "c10": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-80),
    "c12": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-90),
    "c14": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.static.base", 105-105),

    "product-color": "rgba(0, 144, 208, 1)", // override in product
    "strong-main": "product-color",
    "a-bit-transparent": "rgba(0, 0, 0, 0.4)",

    // main
    "background-main": "c01",
    "background-main-1": "c02",
    "background-main-2": "c03",
    "background-main-3": "c04",
    "background-main-4": "c05",
    "background-main-5": "c06",

    "background-card-overlay": "rgba(25, 33, 37, 0.8)",
    "background-workspace-card-overlay": "rgb(35, 93, 122)",

    "navigation_bar_background_color": "rgba(1, 18, 26, 0.8)",
    "fab_text": "contrasted-text-dark",
    "fab-background": "rgba(255, 255, 255, 0.2)",
    "input_background": "#213248",
    "input_background_disable": "rgba(113, 157, 181, 0.25)",
    "hint-background": "rgba(82, 82, 82, 1)",
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
    "bg-shadow": "background-main-5",
    "box-shadow": "rgba(0, 0, 0, 0.15)",
    "shadow": qx.core.Environment.get("css.rgba") ? "a-bit-transparent" : "bg-shadow",

    // window
    "window-popup-background": "rgba(66, 66, 66, 1)",
    "window-caption-background": "background-main",
    "window-caption-background-active": "background-main-3",
    "window-caption-text": "text",
    "window-caption-text-active": "c12",
    "window-border": "background-main-2",
    "window-border-inner": "background-main-1",

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
    "background-selected-disabled": "default-button-disabled",
    "background-selected-dark": "product-color",
    "background-disabled": "background-main",
    "background-disabled-checked": "background-main-1",
    "background-pane": "background-main",

    // tabview
    "tabview-unselected": "c14",
    "tabview-button-border": "product-color",
    "tabview-label-active-disabled": "c10",
    "tabview-pane-background": "transparent",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive": "background-main-4",
    "scrollbar-active": "background-main-5",

    // form
    "button": "background-main-4",
    "button-border": "background-main-5",
    "button-border-hovered": "c07",
    "button-box": "background-main-3",
    "button-box-pressed": "background-main-4",
    "border-lead": "c07",

    // group box
    "white-box-border": "background-main-2",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border": "background-main-3",
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
    "table-focus-indicator": "background-main-5",

    // used in table code
    "table-header-cell": "background-main",
    "table-row-background-focused-selected": "background-main-4",
    "table-row-background-focused": "background-main-3",
    "table-row-background-selected": "background-main-4",
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
    "progressive-progressbar-background": "background-main",
    "progressive-progressbar-indicator-done": "background-main",
    "progressive-progressbar-indicator-undone": "background-main-1",
    "progressive-progressbar-percent-background": "background-main",
    "progressive-progressbar-percent-text": "background-main-1",



    // OSPARC
    "workbench-edge-comp-active": "#777777",
    "workbench-edge-api-active": "#BBBBBB",
    "workbench-start-hint": "#505050",
    "workbench-view-navbar": "c00",
    "workbench-view-splitter": "#000000",

    "node-background": "rgba(113, 157, 181, 0.5)",
    "node-selected-background": "strong-main",
    "node-title-text": "text-selected",
    "node-port-text": "#454545",

    "logger-debug-message": "#FFFFFF",
    "logger-info-message": "#FFFFFF",

    "service-window-hint": "#808080",

    "progressbar": "success",
    "progressbar-disabled": "rgba(113, 157, 181, 0.25)",
    "progressbar-runner": "rgba(228, 234, 237, 0.5)",

    "haloProgressbar": "progressbar",
    "haloProgressbar-disabled": "progressbar-disabled",
    "haloProgressbar-runner": "progressbar-runner",
    "haloProgressbar-fill": "background-card-overlay",

    "loading-page-background-color": "#202020",
    "loading-page-text": "#FFFFFF",
    "loading-page-spinner": "#DDDDDD"
  }
});
