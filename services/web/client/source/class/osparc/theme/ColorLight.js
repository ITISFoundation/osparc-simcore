qx.Theme.define("osparc.theme.ColorLight", {
  extend: osparc.theme.osparclight.Color,
  include: osparc.theme.mixin.Color,
  colors: {
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
    "loading-page-spinner": "#222222",

    "contrasted-background++": "#BBB",
    "scrollbar-passive": "contrasted-background+",
    "scrollbar-active": "contrasted-background++"
  }
});
