/* ************************************************************************

  Purple based theme for Qooxdoo

  Copyright:
     2020 IT'IS Foundation

  License:
     MIT: https://opensource.org/licenses/MIT
     See the LICENSE file in the project's top-level directory for details.

  Authors:
    * Odei Maiz (odeimaiz)

************************************************************************ */
/**
 * Purple color theme based on the the dark theme
 */

qx.Theme.define("osparc.theme.purple.Color", {
  colors: {
    // main
    "background-main": "#202020", // background
    "background-main-lighter": "#24517b", // navbar bg
    "background-main-lighter+": "#315E88", // dashboard button
    "contrasted-background": "#3E6B95", // dashboard button hovered
    "contrasted-background+": "#4A77A1", // dashboard button pressed

    // text
    "text": "#bfbfbf",
    "text-disabled": "#808080",
    "text-selected": "#f0f0f0",
    "text-placeholder": "text-disabled",
    "text-darker": "text-disabled",
    "contrasted-text-dark": "#222222",
    "contrasted-text-light": "#EEEEEE",
    "link": "#aaaaaa",

    // shadows
    "bg-shadow": "#666666",
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
    "material-textfield-focused": "#e0e0e0",
    "material-textfield-disabled": "contrasted-background+",
    "material-textfield-invalid": "#a04040",
    "invalid": "material-textfield-invalid",

    // backgrounds
    "background-selected": "contrasted-background+",
    "background-selected-disabled": "background-main-lighter",
    "background-selected-dark": "contrasted-background",
    "background-disabled": "background-main",
    "background-disabled-checked": "background-main-lighter",
    "background-pane": "background-main",

    // tabview
    "tabview-unselected": "#ffffff",
    "tabview-button-border": "#ffffff",
    "tabview-label-active-disabled": "#d9d9d9",
    "tabview-pane-background": "background-main",
    "tabview-button-background": "transparent",

    // scrollbar
    "scrollbar-passive": "background-main-lighter",
    "scrollbar-active": "contrasted-background",

    // form
    "button": "contrasted-background+",
    "button-border": "bg-shadow",
    "button-border-hovered": "#888888",
    "button-box": "contrasted-background",
    "button-box-pressed": "contrasted-background+",
    "border-lead": "#888888",

    // window
    "window-border": "contrasted-background",
    "window-border-inner": "background-main",

    // group box
    "white-box-border": "#404040",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border": "#484848",
    "border-focused": "#B7B7B7",
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
    "table-header-border": "#888888",
    "table-focus-indicator": "#757575",

    // used in table code
    "table-header-cell": "background-main",
    "table-row-background-focused-selected": "#565656",
    "table-row-background-focused": "#454545",
    "table-row-background-selected": "#565656",
    "table-row-background-even": "background-main",
    "table-row-background-odd": "background-main-lighter",

    // foreground
    "table-row-selected": "text-selected",
    "table-row": "text",

    // table grid color
    "table-row-line": "background-main",
    "table-column-line": "background-main",

    // used in progressive code
    "progressive-table-header": "#AAAAAA",
    "progressive-table-row-background-even": "background-main",
    "progressive-table-row-background-odd": "background-main-lighter",
    "progressive-progressbar-background": "#000000",
    "progressive-progressbar-indicator-done": "background-main",
    "progressive-progressbar-indicator-undone": "background-main-lighter",
    "progressive-progressbar-percent-background": "#000000",
    "progressive-progressbar-percent-text": "background-main-lighter"
  }
});
