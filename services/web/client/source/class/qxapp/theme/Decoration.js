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
        width: 1
      }
    }
  }
});
