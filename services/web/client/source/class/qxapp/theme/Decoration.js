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
        width: 1,
        color: "border",
        transitionProperty: "height",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "panelview-content-noborder": {
      style: {
        transitionProperty: "height",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "outputPortHighlighted": {
      decorator: qx.ui.decoration.MBoxShadow,
      style: {
        shadowColor: "button-border-hovered",
        shadowBlurRadius: 3,
        shadowSpreadRadius: 2,
        shadowLength: [0, 0],
        inset: true
      }
    },

    "window-small-cap": {
      include: "window",
      style: {
        width: 0,
        radius: 3
      }
    },

    "workbench-small-cap-captionbar": {
      style: {
        width: 0
      }
    },

    "sidepanel": {
      style: {
        transitionProperty: ["left"],
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "window-small-cap": {
      include: "window",
      style: {
        width: 0,
        radius: 3
      }
    },

    "workbench-small-cap-captionbar": {
      style: {
        width: 0
      }
    },

    "sidepanel": {
      style: {
        transitionProperty: ["left"],
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    }
  }
});
