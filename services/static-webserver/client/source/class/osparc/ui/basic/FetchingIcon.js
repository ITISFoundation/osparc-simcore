/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Small and simple icon button to trigger different actions on tap.
 */
qx.Class.define("osparc.ui.basic.FetchingIcon", {
  extend: qx.ui.basic.Atom,
  include: osparc.ui.mixin.FetchButton,

  construct: function() {
    this.base(arguments);

    this.set({
      iconSize: 24,
      alignX: "center",
    });

    this.addListener("changeFetching", function(e) {
      const isFetching = e.getData();
      this.setVisibility(isFetching ? "visible" : "excluded");
    }, this);
  },
});
