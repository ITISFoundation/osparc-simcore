/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Theme.define("qxapp.theme.Appearance", {
  extend: osparc.theme.osparcdark.Appearance,

  appearances: {
    "pb-list": {
      include: "list",
      alias:   "list",
      style: function(states) {
        return {
          decorator: null,
          padding: [0, 0]
        };
      }
    },
    "pb-listitem":  {
      // FIXME
      include: "material-button",
      // alias:   "material-button",
      style: function(states) {
        let style = {
          decorator: null,
          padding: 0,
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.backgroundColor = "#444";
        }
        if (states.selected) {
          style.backgroundColor = "#555";
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
    /*
    ---------------------------------------------------------------------------
      PanelView
    ---------------------------------------------------------------------------
    */
    "panelview-titlebar": {
      style: state => ({
        height: 24,
        padding: [0, 5]
      })
    },
    "panelview-titlebar-label": {
      style: state => ({
        marginTop: 4
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
        height: 50
      })
    }
  }
});
