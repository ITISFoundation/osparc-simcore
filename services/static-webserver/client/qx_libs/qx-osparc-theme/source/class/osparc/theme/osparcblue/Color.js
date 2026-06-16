/* ************************************************************************

  OSparc Dark Theme for Qooxdoo

  Copyright:
     2018 IT'IS Foundation

  License:
     MIT: https://opensource.org/licenses/MIT
     See the LICENSE file in the project's top-level directory for details.

  Authors:
    * Tobias Oetiker (oetiker)

  Origin:
    This theme is based in large parts on the the Simple
    theme included with Qooxdoo.
************************************************************************ */
/**
 * Simple color theme
 */

qx.Theme.define("osparc.theme.osparcblue.Color", {
  colors: {
    // main
    "background-main": "#ffffff",
    "primary-color": "#3366aa",
    "primary-color-light": "#6993dc",
    "primary-color-dark": "#003c7a",
    "secondary-color": "#cfd8dc",
    "secondary-color-light": "#ffffff",
    "secondary-color-dark": "#9ea7aa",
    "contrasted-background": "#ffffff",
    "invalid-color": "#a04040",
    "text": "#000000",
    "text-disabled": "#bbb",
    "text-selected": "secondary-color-light",
    "text-placeholder": "#aaa",
    "text-darker": "text-disabled",
    "contrasted-text-dark": "#DDDDDD",
    "contrasted-text-light": "#111111",

    // window
    "window-caption-background": "secondary-color",
    "window-caption-background-active": "primary-color",
    "window-caption-text": "text",
    "window-caption-text-active": "text-selected",

    // material-button
    "material-button-background": "primary-color",
    "material-button-background-hovered": "primary-color-light",
    "material-button-background-pressed": "primary-color-light",
    "material-button-background-disabled": "secondary-color-dark",
    "material-button-text-disabled": "#eeeeee",
    "material-button-text": "#ffffff",

    // material-textfield
    "material-textfield": "primary-color",
    "material-textfield-focused": "primary-color-light",
    "material-textfield-disabled": "secondary-color",
    "material-textfield-invalid": "invalid-color",

    // backgrounds
    "background-selected": "primary-color",
    "background-selected-disabled": "secondary-color-dark",
    "background-selected-dark": "primary-color-dark",
    "background-disabled": "contrasted-background",
    "background-disabled-checked": "contrasted-background",
    "background-pane": "contrasted-background",

    // tabview
    "tabview-unselected": "#1866B5",
    "tabview-button-border": "#134983",
    "tabview-label-active-disabled": "#D9D9D9",
    "tabview-pane-background": "background-pane",
    "tabview-button-background": "transparent",

    // text colors
    "link": "#aaa",

    // scrollbar
    "scrollbar-passive": "#efefef",
    "scrollbar-active": "#e0e0e0",

    // form
    "button": "material-button-background",
    "button-border": "material-button-background",
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

    // shadows
    "shadow": "rgba(0, 0, 0, 0.4)",

    // borders
    // 'border-main' is an alias of 'background-selected' (compatibility reasons)
    "border": "secondary-color",
    "border-focused": "primary-color-light",
    "border-invalid": "invalid-color",
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
    "progressive-progressbar-percent-text": "#333"
  }
});
