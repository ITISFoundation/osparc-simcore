/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.organizations.TutorialsList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._add(this.__createIntroText());
    this._add(this.__getTutorialsFilter());
    this._add(this.__getTutorialsList(), {
      flex: 1
    });
  },

  members: {
    __currentOrg: null,
    __tutorialsModel: null,

    setCurrentOrg: function(orgModel) {
      if (orgModel === null) {
        return;
      }
      this.__currentOrg = orgModel;
      this.__reloadOrgTutorials();
    },

    __createIntroText: function() {
      const msg = this.tr("This is the list of Tutorials shared with this Organization");
      const intro = new qx.ui.basic.Label().set({
        value: msg,
        alignX: "left",
        rich: true,
        font: "text-13"
      });
      return intro;
    },

    __getTutorialsFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "organizationTutorialsList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getTutorialsList: function() {
      const templatesUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3
      });

      const templatesModel = this.__tutorialsModel = new qx.data.Array();
      const templatesCtrl = new qx.data.controller.List(templatesModel, templatesUIList, "name");
      templatesCtrl.setDelegate({
        createItem: () => new osparc.desktop.organizations.SharedResourceListItem("template"),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("uuid", "model", null, item, id);
          ctrl.bindProperty("uuid", "key", null, item, id);
          ctrl.bindProperty("orgId", "orgId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitleMD", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", {
            converter: data => data.get(item.getOrgId())
          }, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationTutorialsList");
          item.addListener("openMoreInfo", e => {
            const templateId = e.getData()["key"];
            osparc.store.Templates.getTutorial(templateId)
              .then(templateData => {
                if (templateData) {
                  templateData["resourceType"] = "tutorial";
                  const {
                    resourceDetails,
                  } = osparc.dashboard.ResourceDetails.popUpInWindow(templateData);
                  resourceDetails.set({
                    showOpenButton: false
                  });
                }
              });
          });
        }
      });

      return templatesUIList;
    },

    __reloadOrgTutorials: function() {
      const templatesModel = this.__tutorialsModel;
      templatesModel.removeAll();

      const orgModel = this.__currentOrg;
      if (orgModel === null) {
        return;
      }

      osparc.store.Templates.getTutorials()
        .then(tutorials => {
          const groupId = orgModel.getGroupId();
          const orgTemplates = tutorials.filter(template => groupId in template["accessRights"]);
          orgTemplates.forEach(orgTemplate => {
            const orgTemplateCopy = osparc.utils.Utils.deepCloneObject(orgTemplate);
            orgTemplateCopy["orgId"] = groupId;
            templatesModel.append(qx.data.marshal.Json.createModel(orgTemplateCopy));
          });
        });
    }
  }
});
