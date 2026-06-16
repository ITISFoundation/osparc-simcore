/* ************************************************************************

  Light Blue based theme for Qooxdoo

  Copyright:
     2020 IT'IS Foundation

  License:
     MIT: https://opensource.org/licenses/MIT
     See the LICENSE file in the project's top-level directory for details.

  Authors:
    * Odei Maiz (odeimaiz)

  Origin:
    This theme is based in large parts on the the Simple
    theme included with Qooxdoo.
************************************************************************ */
/**
 * Light Blue color theme based on the the light theme
 */
qx.Theme.define("osparc.theme.lightblue.Color", {
  colors: {
    // main
    "background-main": "#FFFFFF", // background
    "background-main-lighter": "#D8E3F1", // navbar bg
    "background-main-lighter+": "#BFCAD8", // dashboard button
    "contrasted-background": "#9CAFC9", // dashboard button hovered
    "contrasted-background+": "#8396B0", // dashboard button pressed

    // text
    "text": "#404040",
    "text-disabled": "#7F7F7F",
    "text-selected": "#0F0F0F",
    "text-placeholder": "text-disabled",
    "text-darker": "text-disabled",
    "contrasted-text-dark": "#DDDDDD",
    "contrasted-text-light": "#111111",
    "link": "#555555",

    // shadows
    "bg-shadow": "#999999",
    "shadow": qx.core.Environment.get("css.rgba") ? "rgba(1.0, 1.0, 1.0, 0.4)" : "bg-shadow",

    // window
    "window-caption-background": "background-main",
    "window-caption-background-active": "contrasted-background",
    "window-caption-text": "text",
    "window-caption-text-active": "text-selected",

    // material-button
    "material-button-background": "background-main-lighter+",
    "material-button-background-disabled": "background-main-lighter",
    "material-button-background-hovered": "contrasted-background+",
    "material-button-background-pressed": "contrasted-background+",
    "material-button-text-disabled": "text-disabled",
    "material-button-text": "text",

    // material-textfield
    "material-textfield": "text-disabled",
    "material-textfield-focused": "#1F1F1F",
    "material-textfield-disabled": "contrasted-background+",
    "material-textfield-invalid": "#5FBFBF",
    "invalid": "material-textfield-invalid",

    // backgrounds
    "background-selected": "contrasted-background+",
    "background-selected-disabled": "background-main-lighter",
    "background-selected-dark": "contrasted-background",
    "background-disabled": "background-main",
    "background-disabled-checked": "background-main-lighter",
    "background-pane": "background-main",

    // tabview
    "tabview-unselected": "#000000",
    "tabview-button-border": "#000000",
    "tabview-label-active-disabled": "#262626",
    "tabview-pane-background": "background-main",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive": "background-main-lighter",
    "scrollbar-active": "contrasted-background",

    // form
    "button": "contrasted-background+",
    "button-border": "bg-shadow",
    "button-border-hovered": "#777777",
    "button-box": "contrasted-background",
    "button-box-pressed": "contrasted-background+",
    "border-lead": "#777777",

    // window
    "window-border": "contrasted-background",
    "window-border-inner": "background-main",

    // group box
    "white-box-border": "#BFBFBF",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border": "#B7B7B7",
    "border-focused": "#484848",
    "border-invalid": "material-textfield-invalid",
    "border-disabled": "background-main",

    // separator
    "border-separator": "text-disabled",

    // tooltip
    "tooltip": "text-disabled",
    "tooltip-text": "text-selected",

    // table
    "table-header": "background-main",
    "table-header-foreground": "text",
    "table-header-border": "#777777",
    "table-focus-indicator": "#8A8A8A",

    // used in table code
    "table-header-cell": "background-main",
    "table-row-background-focused-selected": "#A9A9A9",
    "table-row-background-focused": "#BABABA",
    "table-row-background-selected": "#A9A9A9",
    "table-row-background-even": "background-main",
    "table-row-background-odd": "background-main-lighter",

    // foreground
    "table-row-selected": "text-selected",
    "table-row": "text",

    // table grid color
    "table-row-line": "background-main",
    "table-column-line": "background-main",

    // used in progressive code
    "progressive-table-header": "#555555",
    "progressive-table-row-background-even": "background-main",
    "progressive-table-row-background-odd": "background-main-lighter",
    "progressive-progressbar-background": "#FFFFFF",
    "progressive-progressbar-indicator-done": "background-main",
    "progressive-progressbar-indicator-undone": "background-main-lighter",
    "progressive-progressbar-percent-background": "#FFFFFF",
    "progressive-progressbar-percent-text": "background-main-lighter"
  }
});
