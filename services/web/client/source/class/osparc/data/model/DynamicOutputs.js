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

qx.Class.define("osparc.data.model.DynamicOutputs", {
  statics: {
    setOutput: function(metaData, key, type, value, label, description) {
      const outputs = metaData["outputs"];
      if (key === undefined || !Object.keys(outputs).includes(key)) {
        return;
      }

      outputs[key] = {
        type,
        value,
        label,
        description: description || (qx.locale.Manager.tr("List of ") + type)
      };
    },

    addOutput: function(metaData, key, type, label, description) {
      const outputs = metaData["outputs"];
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
        description: description || (qx.locale.Manager.tr("List of ") + type)
      };
    },

    removeOutput: function(metaData, key) {
      const outputs = metaData["outputs"];
      if (key === undefined || !Object.keys(outputs).includes(key)) {
        return;
      }

      delete outputs[key];
    }
  }
});
