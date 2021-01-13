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

qx.Class.define("osparc.component.study.Import", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    const extensions = ["zip"];
    const multiple = false;
    const fileInput = new osparc.ui.form.FileInput(extensions, multiple);
    this._add(fileInput);

    const importBtn = new qx.ui.form.Button(this.tr("Import")).set({
      alignX: "right",
      allowGrowX: false
    });
    this._add(importBtn);
  },

  events: {
    "studyImported": "qx.event.type.Data"
  }
});
