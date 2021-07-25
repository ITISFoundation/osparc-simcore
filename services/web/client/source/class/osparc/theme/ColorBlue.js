qx.Theme.define("osparc.theme.ColorBlue", {
  extend: osparc.theme.osparcblue.Color,
  include: osparc.theme.mixin.Color,
  colors: {
    // main
    "background-main": "#ffffff",
    "background-main-lighter": "#8F8CFF",
    "background-main-lighter+": "#A8A5FF",
    "contrasted-background": "#C2BFFF",
    "contrasted-background+": "#DBD8FF",

    // text
    "text": "#202020",
    "text-disabled": "#303030",
    "text-selected": "#0F0F0F",
    "text-placeholder": "text-disabled",
    "text-darker": "text-disabled",
    "contrasted-text-dark": "#DDDDDD",
    "contrasted-text-light": "#111111",
    "link": "#aaaaaa",

    // shadows
    "bg-shadow": "#999999",
    "shadow": qx.core.Environment.get("css.rgba") ? "rgba(255, 255, 255, 0.4)" : "bg-shadow",

    // window
    "window-caption-background": "background-main",
    "window-caption-background-active": "contrasted-background",
    "window-caption-text": "text",
    "window-caption-text-active": "text-selected",

    // material-button
    "material-button-background": "background-main-lighter+",
    "material-button-background-hovered": "background-main-lighter",
    "material-button-background-pressed": "contrasted-background",
    "material-button-background-disabled": "contrasted-background",
    "material-button-text-disabled": "text-disabled",
    "material-button-text": "text",





    "primary-color": "background-main-lighter",
    "primary-color-light": "#6993dc",
    "primary-color-dark": "#003c7a",
    "secondary-color": "#cfd8dc",
    "secondary-color-light": "#ffffff",
    "secondary-color-dark": "#9ea7aa",
    "invalid-color": "#a04040",

    // material-textfield
    "material-textfield": "primary-color",
    "material-textfield-focused": "primary-color-light",
    "material-textfield-disabled": "secondary-color",
    "material-textfield-invalid": "invalid-color",

    // backgrounds
    "background-selected": "primary-color",
    "background-selected-disabled": "secondary-color-dark",
    "background-selected-dark": "primary-color-dark",
    "background-disabled": "background-main",
    "background-disabled-checked": "contrasted-background",
    "background-pane": "contrasted-background",

    // tabview
    "tabview-unselected": "#1866B5",
    "tabview-button-border": "#134983",
    "tabview-label-active-disabled": "#D9D9D9",
    "tabview-pane-background": "background-main",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive": "#efefef",
    "scrollbar-active": "#e0e0e0",

    // form
    "button": "material-button-background",
    "button-border": "bg-shadow",
    "button-border-hovered": "material-button-background-hovered",
    "invalid": "invalid-color",
    "button-box": "material-button-background",
    "button-box-pressed": "material-button-background-pressed",
    "border-lead": "primary-color",

    // window
    "window-border": "secondary-color",
    "window-border-inner": "secondary-color",

    // group box
    "white-box-border": "rgba(0,0,0,0.2)",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border": "secondary-color",
    "border-focused": "primary-color-light",
    "border-invalid": "material-textfield-invalid",
    "border-disabled": "material-button-text-disabled",

    // separator
    "border-separator": "#808080",

    // tooltip
    "tooltip": "primary-color-light",
    "tooltip-text": "#f0f0f0",

    // table
    "table-header": "contrasted-background",
    "table-header-foreground": "text",
    "table-header-border":  "primary-color-dark",
    "table-focus-indicator": "primary-color-dark",

    // used in table code
    "table-header-cell": "contrasted-background",
    "table-row-background-focused-selected": "primary-color",
    "table-row-background-focused": "primary-color",
    "table-row-background-selected": "primary-color-light",
    "table-row-background-even": "secondary-color",
    "table-row-background-odd": "contrasted-background",

    // foreground
    "table-row-selected": "#ffffff",
    "table-row": "text",

    // table grid color
    "table-row-line": "secondary-color",
    "table-column-line": "secondary-color",

    // used in progressive code
    "progressive-table-header": "#AAAAAA",
    "progressive-table-row-background-even": "#202020",
    "progressive-table-row-background-odd": "#303030",
    "progressive-progressbar-background": "#000",
    "progressive-progressbar-indicator-done": "#222",
    "progressive-progressbar-indicator-undone": "#333",
    "progressive-progressbar-percent-background": "#000",
    "progressive-progressbar-percent-text": "#333",








    "workbench-edge-comp-active": "#888888",
    "workbench-edge-api-active": "#444444",
    "workbench-edge-selected": "#FFFF00",
    "workbench-start-hint": "#AFAFAF",

    "node-selected-background": "#999999",
    "node-title-text": "#232323",
    "node-port-text": "#454545",

    "logger-debug-message": "#000000",
    "logger-info-message": "#000000",
    "logger-warning-message": "#FFFF00",
    "logger-error-message": "#FF0000",

    "service-window-hint": "#7F7F7F",

    "progressbar": "#9F6F61",

    "loading-page-background-color": "background-main",
    "loading-page-text": "#000000",
    "loading-page-spinner": "#222222"
  }
});
