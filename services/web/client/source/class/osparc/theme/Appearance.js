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
  extend: osparc.theme.osparcdark.Appearance,

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
          backgroundColor: "background-main-lighter+"
        };
        if (states.hovered) {
          style.backgroundColor = "#444";
        }
        if (states.selected || states.checked) {
          style.backgroundColor = "#555";
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
          style.backgroundColor = "background-main-lighter+";
        }
        if (states.selected || states.checked) {
          style.backgroundColor = "#444";
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
          backgroundColor: "background-selected-dark",
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
          backgroundColor: "background-selected-dark",
          decorator: "workbench-small-cap-captionbar"
        };
      }
    },

    "window-small-cap/title": {
      include: "window/title",
      style: function(states) {
        return {
          marginLeft: 2,
          font: "small"
        };
      }
    },

    "window-small-cap/minimize-button": {
      alias: "window/minimize-button",
      include: "window/minimize-button",
      style: function(states) {
        return {
          icon: osparc.theme.osparcdark.Image.URLS["window-minimize"]+"/14"
        };
      }
    },

    "window-small-cap/restore-button": {
      alias: "window/restore-button",
      include: "window/restore-button",
      style: function(states) {
        return {
          icon: osparc.theme.osparcdark.Image.URLS["window-restore"]+"/14"
        };
      }
    },

    "window-small-cap/maximize-button": {
      alias: "window/maximize-button",
      include: "window/maximize-button",
      style: function(states) {
        return {
          icon: osparc.theme.osparcdark.Image.URLS["window-maximize"]+"/14"
        };
      }
    },

    "window-small-cap/close-button": {
      alias: "window/close-button",
      include: "window/close-button",
      style: function(states) {
        return {
          icon: osparc.theme.osparcdark.Image.URLS["window-close"]+"/14"
        };
      }
    },

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
        backgroundColor: "material-button-background",
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
        backgroundColor: "material-button-background"
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
        font: "title-14"
      })
    },
    "panelview-titlebar": {
      style: state => ({
        height: 24,
        padding: [0, 5],
        alignY: "middle",
        cursor: "pointer"
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
        backgroundColor: "background-main-lighter"
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
        backgroundColor: "background-main-lighter+"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Jumbo
    ---------------------------------------------------------------------------
    */
    "jumbo": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        padding: [7, 8, 5, 8]
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
        decorator: "link-button",
        backgroundColor: "transparent",
        textColor: state.hovered ? "text" : "text-darker"
      })
    },

    "big-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 50,
        center: true
      })
    },

    "big-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "md-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 35,
        center: true
      })
    },

    "md-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "text-16"
      })
    },

    /*
    ---------------------------------------------------------------------------
      FlashMessage
    ---------------------------------------------------------------------------
    */
    "flash": {
      style: state => ({
        padding: 10,
        backgroundColor: "background-main-lighter+",
        decorator: "flash"
      })
    },
    "flash/badge": {
      style: state => ({
        decorator: "flash-badge"
      })
    },

    /*
    ---------------------------------------------------------------------------
      IFrame
    ---------------------------------------------------------------------------
    */
    "iframe": {},

    /*
    ---------------------------------------------------------------------------
      GroupBox
    ---------------------------------------------------------------------------
    */
    "settings-groupbox": {
      include: "groupbox",
      alias: "groupbox"
    },
    "settings-groupbox/frame": {
      include: "groupbox/frame",
      style: state => ({
        decorator: "no-border"
      })
    },
    "settings-groupbox/legend": {
      alias: "atom",
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
        backgroundColor: "background-main-lighter+",
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
        backgroundColor: "background-main-lighter",
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
        decorator: state.hovered ? "border-editable" : null,
        marginLeft: state.hovered ? 0 : 1,
        padding: 2,
        cursor: "text"
      })
    },
    "editlabel/input": {
      include: "textfield",
      style: state => ({
        paddingTop: 4,
        paddingLeft: 3,
        minWidth: 80
      })
    }
  }
});
