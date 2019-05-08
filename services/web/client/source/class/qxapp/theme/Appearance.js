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
          padding: [0, 0],
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
          decorator: "window-small-cap"
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
      style: (state, styles) => {
        styles.margin = [7, 10];
        styles.paddingLeft = 5;
        return styles;
      }
    },
    "toolbar-selectbox/arrow": {
      include: "selectbox/arrow",
      style: (state, style) => {
        style.cursor = "pointer";
        return style;
      }
    },
    "toolbar-selectbox/list": {
      include: "selectbox/list",
      style: (state, style) => {
        style.padding = 0;
        return style;
      }
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
    }
  }
});
