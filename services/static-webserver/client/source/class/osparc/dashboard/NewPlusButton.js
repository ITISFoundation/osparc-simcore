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

qx.Class.define("osparc.dashboard.NewPlusButton", {
  extend: qx.ui.form.MenuButton,

  construct: function() {
    this.base(arguments);

    this.set({
      appearance: "strong-button",
      icon: osparc.dashboard.CardBase.NEW_ICON + "20",
      label: this.tr("New 102"),
      font: "text-16",
      gap: 15,
      padding: 15,
      paddingRight: 20,
      allowGrowX: false,
    });

    osparc.utils.Utils.setIdToWidget(this, "newPlusBtn");

    this.setMenu(new osparc.dashboard.NewPlusMenu());
  },
});
