/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Theme.define("osparc.theme.Appearance", {
  extend: osparc.theme.common.Appearance,

  appearances: {
    "pb-list": {
      include: "list",
      alias:   "list",
      style: function(states) {
        return {
          decorator: null,
          padding: 0
        };
      }
    },
    "pb-listitem":  {
      include: "material-button",
      style: function(states) {
        const style = {
          decorator: "pb-listitem",
          padding: 5,
          backgroundColor: "background-main-2"
        };
        if (states.hovered) {
          style.backgroundColor = "background-main-3";
        }
        if (states.selected || states.checked) {
          style.backgroundColor = "background-main-4";
        }
        return style;
      }
    },
    "selectable": {
      include: "material-button",
      style: function(states) {
        const style = {
          decorator: "no-radius-button",
          padding: 5,
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.backgroundColor = "background-main-2";
        }
        if (states.selected || states.checked) {
          style.backgroundColor = "background-main-3";
        }
        return style;
      }
    },

    /*
    ---------------------------------------------------------------------------
      WINDOW-SMALL-CAP CHOOSER
    ---------------------------------------------------------------------------
    */
    "window-small-cap": {
      include: "window", // get all the settings from window
      alias: "window", // redirect kids to window/kid
      style: function(states) {
        return {
          backgroundColor: states.selected ? "node-selected-background" : "background-selected-dark",
          decorator: states.maximized ? "window-small-cap-maximized" : "window-small-cap"
        };
      }
    },

    "window-small-cap/captionbar": {
      include: "window/captionbar", // load defaults from window captionbar
      alias: "window/captionbar", // redirect kids
      style: function(states) {
        return {
          padding: [0, 3, 0, 3],
          minHeight: 20,
          backgroundColor: "transparent",
          decorator: "workbench-small-cap-captionbar"
        };
      }
    },

    "window-small-cap/title": {
      include: "window/title",
      style: function(states) {
        return {
          marginLeft: 2,
          font: "text-12"
        };
      }
    },

    "window-small-cap/minimize-button": {
      alias: "window/minimize-button",
      include: "window/minimize-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-minimize"]+"/14"
        };
      }
    },

    "window-small-cap/restore-button": {
      alias: "window/restore-button",
      include: "window/restore-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-restore"]+"/14"
        };
      }
    },

    "window-small-cap/maximize-button": {
      alias: "window/maximize-button",
      include: "window/maximize-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-maximize"]+"/14"
        };
      }
    },

    "window-small-cap/close-button": {
      alias: "window/close-button",
      include: "window/close-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-close"]+"/14"
        };
      }
    },

    "window-small-cap/progress": "progressbar",

    "service-window": {
      include: "window",
      alias: "window",
      style: state => ({
        decorator: state.maximized ? "service-window-maximized" : "service-window"
      })
    },
    "service-window/captionbar": {
      include: "window/captionbar",
      style: state => ({
        backgroundColor: "background-main-2",
        decorator: "workbench-small-cap-captionbar"
      })
    },
    "info-service-window": {
      include: "service-window",
      alias: "service-window",
      style: state => ({
        maxHeight: state.maximized ? null : 500
      })
    },

    "dialog-window-content": {
      style: () => ({
        backgroundColor: "background-main-2"
      })
    },
    /*
    ---------------------------------------------------------------------------
      PanelView
    ---------------------------------------------------------------------------
    */
    "panelview": {
      style: state => ({
        decorator: "panelview"
      })
    },
    "panelview/title": {
      style: state => ({
        font: "title-14",
        cursor: "pointer"
      })
    },
    "panelview/caret": {
      style: state => ({
        cursor: "pointer"
      })
    },
    "panelview-titlebar": {
      style: state => ({
        height: 24,
        padding: [0, 5],
        alignY: "middle"
      })
    },
    "panelview-content": {
      style: state => ({
        decorator: "panelview-content",
        margin: [0, 4, 4, 4]
      })
    },

    /*
    ---------------------------------------------------------------------------
      Toolbar
    ---------------------------------------------------------------------------
    */
    "toolbar-textfield": {
      include: "material-textfield",
      style: state => ({
        backgroundColor: "transparent",
        marginTop: 8
      })
    },
    "toolbar-label": {
      style: state => ({
        marginTop: 11,
        marginRight: 3
      })
    },
    "textfilter": {},
    "textfilter/textfield": "toolbar-textfield",

    "autocompletefilter": {},
    "autocompletefilter/autocompletefield/textfield": {
      include: "toolbar-textfield",
      style: state => ({
        paddingRight: 15
      })
    },
    "autocompletefilter/autocompletefield/button": {},

    "toolbar-selectbox": {
      include: "textfield",
      alias: "selectbox",
      style: () => ({
        margin: [7, 10],
        paddingLeft: 5
      })
    },
    "toolbar-selectbox/arrow": {
      include: "selectbox/arrow",
      style: style => ({
        cursor: style.disabled ? "auto" : "pointer"
      })
    },
    "toolbar-selectbox/list": {
      include: "selectbox/list",
      style: () => ({
        padding: 0
      })
    },

    "toolbar-progressbar": {
      include: "progressbar",
      alias: "progressbar",
      style: () => ({
        margin: [7, 10]
      })
    },

    /*
    ---------------------------------------------------------------------------
      SidePanel
    ---------------------------------------------------------------------------
    */
    sidepanel: {
      style: state => ({
        backgroundColor: "background-main-1"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Splitpane
    ---------------------------------------------------------------------------
    */
    "splitpane/splitter": {
      style: state => ({
        visible: false
      })
    },

    /*
    ---------------------------------------------------------------------------
      NodePorts
    ---------------------------------------------------------------------------
    */
    "node-ports": {
      style: state => ({
        backgroundColor: "background-main-2"
      })
    },

    /*
    ---------------------------------------------------------------------------
      ServiceBrowser
    ---------------------------------------------------------------------------
    */
    "service-browser": {
      style: state => ({
        padding: 8,
        decorator: "service-browser"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Buttons
    ---------------------------------------------------------------------------
    */
    "link-button": {
      include: "material-button",
      style: state => ({
        backgroundColor: "transparent",
        textColor: state.hovered ? "text" : "text-darker"
      })
    },

    "xl-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 50,
        center: true
      })
    },

    "xl-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "lg-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 35,
        center: true
      })
    },

    "lg-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "text-16"
      })
    },

    "md-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 25,
        center: true
      })
    },

    "md-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "text-14"
      })
    },

    "toolbar-xl-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 50,
        center: true
      })
    },

    "toolbar-xl-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "toolbar-lg-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 35,
        center: true
      })
    },

    "toolbar-lg-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "text-16"
      })
    },

    "toolbar-md-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 25,
        center: true
      })
    },

    "toolbar-md-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "text-14"
      })
    },

    "no-shadow-button": {
      alias: "atom",
      style: function(states) {
        var decorator = "toolbar-button";
        if (states.hovered || states.pressed || states.checked) {
          decorator += "-hovered";
        }
        return {
          cursor: states.disabled ? undefined : "pointer",
          decorator: decorator,
          textColor: "material-button-text",
          padding: [3, 5]
        };
      }
    },

    // override in product
    "strong-button": {
      include: "material-button",
      style: state => ({
        decorator: state.hovered || state.focused ? "strong-bordered-button" : "no-border",
        backgroundColor: "strong-main",
        textColor: "#d2d8dc" // dark theme's text color
      })
    },

    "danger-button": {
      include: "material-button",
      style: state => ({
        decorator: "bordered-button",
        backgroundColor: state.hovered || state.focused ? "danger-red" : null,
        textColor: state.hovered || state.focused ? "#d2d8dc" : "danger-red" // dark theme's text color
      })
    },

    /*
    ---------------------------------------------------------------------------
      FlashMessage
    ---------------------------------------------------------------------------
    */
    "flash": {
      style: () => ({
        padding: 12,
        backgroundColor: "background-main-3",
        decorator: "flash"
      })
    },
    "flash/badge": {
      style: () => ({
        decorator: "flash-badge"
      })
    },

    /*
    ---------------------------------------------------------------------------
      GroupBox
    ---------------------------------------------------------------------------
    */
    "settings-groupbox": "groupbox",
    "settings-groupbox/frame": {
      include: "groupbox/frame",
      style: state => ({
        decorator: "no-border"
      })
    },
    "settings-groupbox/legend": {
      include: "groupbox/legend",
      style: state => ({
        font: "title-16"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Hints
    ---------------------------------------------------------------------------
    */
    "hint": {
      style: state => ({
        backgroundColor: "background-main-2",
        decorator: "hint",
        padding: 5
      })
    },

    /*
    ---------------------------------------------------------------------------
      Chip
    ---------------------------------------------------------------------------
    */
    "chip": {
      include: "atom",
      alias: "atom",
      style: state => ({
        decorator: "chip",
        backgroundColor: "background-main-1",
        padding: [3, 5]
      })
    },

    "chip/label": {
      include: "atom/label",
      style: state => ({
        font: "text-10"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Dashboard
    ---------------------------------------------------------------------------
    */
    "dashboard": {
      include: "tabview",
      alias: "tabview"
    },

    "dashboard/pane": {
      style: state => ({
        padding: [0, 0, 0, 15]
      })
    },

    "dashboard/bar/content": {
      style: state => ({
        width: 120,
        paddingTop: 15
      })
    },

    "dashboard-page": {
      include: "tabview-page",
      alias: "tabview-page"
    },

    "dashboard-page/button": {
      include: "tabview-page/button",
      alias: "tabview-page/button",
      style: state => ({
        font: state.checked ? "title-16" : "text-16"
      })
    },

    /*
    ---------------------------------------------------------------------------
      EditLabel
    ---------------------------------------------------------------------------
    */
    "editlabel": {},
    "editlabel/label": {
      include: "atom/label",
      style: state => ({
        decorator: state.hovered && state.editable ? "border-editable" : null,
        marginLeft: state.hovered && state.editable ? 0 : 1,
        padding: [2, state.hovered && state.editable ? 2 : 3, 2, 2],
        cursor: state.editable ? "text" : "auto"
      })
    },
    "editlabel/input": {
      include: "textfield",
      style: state => ({
        paddingTop: 4,
        paddingLeft: 3,
        minWidth: 80,
        backgroundColor: "transparent"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Tag
    ---------------------------------------------------------------------------
    */
    "tag": {
      include: "atom/label",
      style: state => ({
        decorator: "tag",
        padding: [1, 5]
      })
    },
    "tagitem": {
      style: () => ({
        decorator: "tagitem",
        padding: 5
      })
    },
    "tagitem/colorbutton": {
      include: "material-button",
      alias: "material-button",
      style: () => ({
        decorator: "tagitem-colorbutton"
      })
    },
    "tagbutton": {
      include: "material-button",
      alias: "material-button",
      style: () => ({
        decorator: "tagbutton"
      })
    },

    "margined-layout": {
      style: () => ({
        margin: [7, 10]
      })
    },

    /*
    ---------------------------------------------------------------------------
      jsonforms
    ---------------------------------------------------------------------------
    */
    "form-array-container": {
      style: () => ({
        padding: 10,
        decorator: "border-editable"
      })
    }
  }
});
