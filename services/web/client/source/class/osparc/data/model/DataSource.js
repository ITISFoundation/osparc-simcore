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

qx.Class.define("osparc.data.model.DataSource", {
  extend: osparc.data.model.Node,

  members: {
    addOutput: function(key, type, label, description) {
      const outputs = this._metaData["outputs"];
      if (key === undefined) {
        key = "out_01";
        const nOuts = Object.keys(outputs).length;
        if (nOuts) {
          const lastOutKey = Object.keys(outputs)[nOuts-1];
          key = "out" + parseInt(lastOutKey.slice(-2)) + 1;
        }
      }
      outputs[key] = {
        type,
        label,
        description: description || (this.tr("List of ") + type)
      };

      this.setOutputs(this._metaData["outputs"]);
    }
  }
});
