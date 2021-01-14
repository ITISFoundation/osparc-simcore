/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.task.Export", {
  extend: osparc.component.task.Task,

  construct: function(study) {
    this.base(arguments);

    this.__study = study;

    this.__builyLayout();
  },

  members: {
    __study: null,

    __builyLayout: function() {
      const fetchButton = this.getChildControl("icon-status");
      fetchButton.setFetching(true);

      const label = this.getChildControl("label");
      label.setValue(this.tr("Exporting: ") + this.__study.name);

      this.getChildControl("icon-stop");
    },

    // overridden
    _stopTask: function() {
      console.log("Stop exporting", this.__study.name);
    }
  }
});
