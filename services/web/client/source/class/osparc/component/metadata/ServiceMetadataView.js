/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.metadata.ServiceMetadataView", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(5, 5);
    grid.setColumnAlign(0, "left", "middle");
    grid.setColumnFlex(0, 1);
    grid.setColumnAlign(1, "left", "middle");
    this._setLayout(grid);

    this.__serviceData = serviceData;

    this.__populateHeaders();
    this.__populateData();
  },

  members: {
    __serviceData: null,

    __populateHeaders: function() {
      const rules = osparc.component.metadata.ServiceMetadata.getMetadataTSR();

      const header0 = new qx.ui.basic.Label(this.tr("Rule"));
      this._add(header0, {
        row: 0,
        column: 0
      });
      const header1 = new qx.ui.basic.Label(this.tr("Conformance Level"));
      this._add(header1, {
        row: 0,
        column: 1
      });

      let row = 1;
      Object.values(rules).forEach(rule => {
        const label = new qx.ui.basic.Label(rule.title);
        const ruleWHint = new osparc.component.form.FieldWHint(null, rule.description, label);
        this._add(ruleWHint, {
          row,
          column: 0
        });
        row++;
      });
    },

    __populateData: function() {
      
    }
  }
});
