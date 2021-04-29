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
    setOutput: function(key, type, label, description) {
      const outputs = this._metaData["outputs"];
      if (key === undefined || !Object.keys(outputs).includes(key)) {
        return;
      }

      outputs[key] = {
        type,
        label,
        description: description || (this.tr("List of ") + type)
      };

      this.setOutputs(this._metaData["outputs"]);
    },

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
    },

    removeOutput: function(key) {
      const outputs = this._metaData["outputs"];
      if (key === undefined || !Object.keys(outputs).includes(key)) {
        return;
      }

      delete outputs[key];

      this.setOutputs(this._metaData["outputs"]);
    }
  }
});
