/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.component.widget.LinkButton", {
  extend: qx.ui.form.Button,

  construct: function(label, url, height = 12) {
    this.base(arguments, label);

    this.set({
      icon: "@FontAwesome5Solid/external-link-alt/"+height,
      iconPosition: "right",
      allowGrowX: false
    });

    this.addListener("execute", () => {
      window.open(url);
    }, this);
  }
});
