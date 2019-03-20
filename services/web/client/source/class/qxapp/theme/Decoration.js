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
    "droppableWidget": {
      decorator: qx.ui.decoration.Decorator,
      style: {
        style: "dashed",
        color: "#828282",
        width: 1
      }
    },

    "draggableWidget": {
      decorator: qx.ui.decoration.Decorator,
      style: {
        color: "#828282",
        width: 1,
        radius: 4
      }
    },

    "panelview-content": {
      decorator: qx.ui.decoration.MSingleBorder,
      style: {
        width: 1,
        color: "border"
      }
    },

    "service-tree": {
      decorator: qx.ui.decoration.MSingleBorder,
      style: {
        width: 0
      }
    },

    "panelview-close-collapse-transition": {
      style: {
        transitionProperty: ["height", "top"],
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "panelview-open-collapse-transition": {
      include: "panelview-content",
      style: {
        transitionProperty: ["height", "top"],
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    }
  }
});
