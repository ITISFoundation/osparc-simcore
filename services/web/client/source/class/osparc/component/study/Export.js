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

qx.Class.define("osparc.component.study.Export", {
  extend: qx.core.Object,

  construct: function(study) {
    this.base(arguments);

    this.study = study;

    const exporter = osparc.component.study.Exporter.getInstance();
    exporter.addExport(this);
  }
});
