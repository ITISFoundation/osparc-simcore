/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.study.ResourceSelector", {
  extend: qx.ui.core.Widget,

  construct: function(studyId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__studyId = studyId;

    const params = {
      url: {
        "studyId": studyId
      }
    };
    osparc.data.Resources.getOne("studies", params)
      .then(studyData => {
        this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
        this.__buildLayout();
      });
  },

  events: {
    "startStudy": "qx.event.type.Event"
  },

  members: {
    __studyId: null,
    __studyData: null,

    __buildLayout: function() {
      this.__buildNodeResources();
    },

    createServiceGroup: function(serviceLabel, serviceResources) {
      const box = new qx.ui.groupbox.GroupBox(serviceLabel);
      console.log(serviceResources);
      return box;
    },

    __buildNodeResources: function() {
      if ("workbench" in this.__studyData) {
        for (const nodeId in this.__studyData["workbench"]) {
          const node = this.__studyData["workbench"][nodeId];
          console.log(node);
          const params = {
            url: {
              studyId: this.__studyId,
              nodeId
            }
          };
          osparc.data.Resources.get("nodesInStudyResources", params)
            .then(serviceResources => {
              const servicegroup = this.createServiceGroup(node["label"], serviceResources);
              this._add(servicegroup);
            });
        }
      }
    }
  }
});
