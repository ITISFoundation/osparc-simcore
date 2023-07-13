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

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__studyId = studyId;

    const loadingImage = new qx.ui.basic.Image().set({
      source: "@FontAwesome5Solid/circle-notch/32",
      alignX: "center",
      alignY: "middle"
    });
    loadingImage.getContentElement().addClass("rotate");
    this._add(loadingImage);

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

  statics: {
    createGroupBox: function(label) {
      const box = new qx.ui.groupbox.GroupBox(label);
      box.getChildControl("legend").set({
        font: "text-14",
        padding: 2
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent",
        padding: 2
      });
      box.setLayout(new qx.ui.layout.VBox(10));
      return box;
    },

    createToolbarRadioButton: function(label, id) {
      const rButton = new qx.ui.toolbar.RadioButton().set({
        label,
        padding: 10,
        minWidth: 35,
        center: true
      });
      rButton.id = id;
      rButton.getContentElement().setStyles({
        "border-radius": "4px"
      });
      return rButton;
    }
  },

  members: {
    __studyId: null,
    __studyData: null,

    __buildLayout: function() {
      this.__buildNodeResources();
    },

    createServiceGroup: function(serviceLabel, servicesResources) {
      const imageKeys = Object.keys(servicesResources);
      if (imageKeys && imageKeys.length) {
        const mainImageKey = imageKeys[0];
        const serviceResources = servicesResources[mainImageKey];
        if (serviceResources && "resources" in serviceResources) {
          const box = this.self().createGroupBox(serviceLabel);
          box.exclude();
          if ("CPU" in serviceResources["resources"]) {
            const opt1 = this.self().createToolbarRadioButton("1", 1);
            const opt2 = this.self().createToolbarRadioButton("2", 2);
            const opt3 = this.self().createToolbarRadioButton("4", 4);

            const group = new qx.ui.form.RadioGroup(opt1, opt2, opt3);
            group.setSelection([opt2]);

            const groupBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
            groupBox.add(opt1);
            groupBox.add(opt2);
            groupBox.add(opt3);

            const cpuBox = this.self().createGroupBox("CPU");
            cpuBox.add(groupBox);
            box.add(cpuBox);
            box.show();
          }
          if ("RAM" in serviceResources["resources"]) {
            const opt1 = this.self().createToolbarRadioButton("256 MB", 256);
            const opt2 = this.self().createToolbarRadioButton("512 MB", 512);
            const opt3 = this.self().createToolbarRadioButton("1024 MB", 1024);

            const group = new qx.ui.form.RadioGroup(opt1, opt2, opt3);
            group.setSelection([opt2]);

            const groupBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
            groupBox.add(opt1);
            groupBox.add(opt2);
            groupBox.add(opt3);

            const ramBox = this.self().createGroupBox("RAM");
            ramBox.add(groupBox);
            box.add(ramBox);
            box.show();
          }
          return box;
        }
      }
      return null;
    },

    __buildNodeResources: function() {
      const servicesBox = this.self().createGroupBox(this.tr("Select Resources"));
      servicesBox.exclude();
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
              this._removeAll();
              this._add(servicesBox);
              const serviceGroup = this.createServiceGroup(node["label"], serviceResources);
              if (serviceGroup) {
                servicesBox.add(serviceGroup);
                servicesBox.show();
              }
            });
        }
      }
    }
  }
});
