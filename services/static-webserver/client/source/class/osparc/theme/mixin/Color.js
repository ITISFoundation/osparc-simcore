qx.Theme.define("osparc.theme.mixin.Color", {
  colors: {
    "activitytree-background-cpu": "#2C7CCE",
    "activitytree-background-memory": "#358475",

    "ready-green": "#58A6FF", // It is not really green because of reasons
    "warning-yellow": "#FFFF00",
    "warning-yellow-s4l": "#f8db1f",
    "busy-orange": "#FFA500",
    "failed-red": "#FF2D2D",
    "danger-red": osparc.theme.colorProvider.ColorProvider.getColor("color.scales.danger", 40),

    "visual-blue": "#007fd4", // Visual Studio blue

    "logger-warning-message": "warning-yellow",
    "logger-error-message": "failed-red",

    "workbench-edge-selected": "busy-orange"
  }
});
