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
        margin: [0, 4, 4, 4]
      })
    },
    "toolbar-textfield": {
      include: "material-textfield",
      style: state => ({
        backgroundColor: "material-button-background",
        marginTop: 8
      })
    },
    "toolbar-label": {
      style: state => ({
        marginTop: 11,
        marginRight: 3
      })
    },
    "splitpane/splitter": {
      style: state => ({
        width: 0
      })
    },
    sidebar: {
      style: state => ({
        backgroundColor: "background-main-lighter"
      })
    }
  }
});
