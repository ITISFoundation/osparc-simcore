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
 * Small and simple loading/fetching indicator component.
 * Displays a visual indicator when a fetching operation is in progress.
 */
qx.Class.define("osparc.ui.basic.FetchingIcon", {
  extend: qx.ui.basic.Atom,
  include: osparc.ui.mixin.FetchButton,

  construct: function() {
    this.base(arguments);

    this.set({
      alignX: "center",
      center: true,
    });

    this.addListener("changeFetching", e => {
      const isFetching = e.getData();
      this.setVisibility(isFetching ? "visible" : "excluded");
    }, this);
  },
});
