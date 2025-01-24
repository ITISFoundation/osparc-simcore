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
      appearance: "pb-new",
      icon: osparc.dashboard.CardBase.NEW_ICON + "26",
      label: this.tr("New"),
      font: "text-16",
      gap: 15,
      padding: 15,
      paddingRight: 20,
      allowGrowX: false,
    });

    osparc.utils.Utils.setIdToWidget(this, "newStudyBtn");

    this.setMenu(new osparc.dashboard.NewPlusMenu());
  },
});
