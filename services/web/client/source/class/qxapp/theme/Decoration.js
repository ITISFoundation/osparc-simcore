/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Theme.define("qxapp.theme.Decoration", {
  extend: osparc.theme.osparcdark.Decoration,

  decorations: {

    "service-tree": {
      decorator: qx.ui.decoration.MSingleBorder,
      style: {
        width: 0
      }
    },

    "panelview": {
      style: {
        transitionProperty: "top",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "panelview-content": {
      style: {
        transitionProperty: "height",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "outputPortHighlighted": {
      style: {
        backgroundColor: "background-main-lighter+"
      }
    },

    "window-small-cap": {
      include: "window",
      style: {
        width: 0,
        radius: 3,
        transitionProperty: "opacity",
        transitionDuration: "0.05s",
        transitionTimingFunction: "ease-in"
      }
    },

    "workbench-small-cap-captionbar": {
      style: {
        width: 0
      }
    },

    "sidepanel": {
      style: {
        transitionProperty: ["left", "width"],
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "service-browser": {
      style: {
        width: 1,
        color: "material-button-background"
      }
    },

    "link-button": {}
  }
});
