/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Widget that displays the services and their versions included in the Study
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *    const servicesInStudy = new osparc.component.metadata.ServicesInStudy(study);
 *    this.add(servicesInStudy);
 * </pre>
 */

qx.Class.define("osparc.component.metadata.ServicesInStudy", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object|osparc.data.model.Study} studyData (metadata)
    */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grid(10));

    this.__studyData = studyData;

    this.__populateLayout();
  },

  members: {
    __populateLayout: function() {
      const nodes = Object.values(this.__studyData.workbench);
      for (let i=0; i<nodes.length; i++) {
        const nameLabel = new qx.ui.basic.Label(nodes[i]["key"]).set({
          font: "text-14"
        });
        const keyLabel = new qx.ui.basic.Label(nodes[i]["key"]).set({
          font: "text-14"
        });
        const versionLabel = new qx.ui.basic.Label(nodes[i]["version"]).set({
          font: "text-14"
        });
        this._add(nameLabel, {
          row: i,
          column: 0
        });
        this._add(keyLabel, {
          row: i,
          column: 1
        });
        this._add(versionLabel, {
          row: i,
          column: 2
        });
      }
    }
  }
});
