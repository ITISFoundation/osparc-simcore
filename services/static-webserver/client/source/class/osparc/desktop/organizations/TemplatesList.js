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

qx.Class.define("osparc.desktop.organizations.TemplatesList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._add(this.__createIntroText());
    this._add(this.__getTemplatesFilter());
    this._add(this.__getTemplatesList(), {
      flex: 1
    });
  },

  members: {
    __currentOrg: null,
    __templatesModel: null,

    setCurrentOrg: function(orgModel) {
      if (orgModel === null) {
        return;
      }
      this.__currentOrg = orgModel;
      this.__reloadOrgTemplates();
    },

    __createIntroText: function() {
      const msg = this.tr("This is the list of ") + osparc.product.Utils.getTemplateAlias({plural: true}) + this.tr(" shared with this Organization");
      const intro = new qx.ui.basic.Label().set({
        value: msg,
        alignX: "left",
        rich: true,
        font: "text-13"
      });
      return intro;
    },

    __getTemplatesFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "organizationTemplatesList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getTemplatesList: function() {
      const templatesUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3
      });

      const templatesModel = this.__templatesModel = new qx.data.Array();
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
          item.subscribeToFilterGroup("organizationTemplatesList");
          item.addListener("openMoreInfo", e => {
            const templateId = e.getData()["key"];
            osparc.data.Resources.get("templates")
              .then(templates => {
                const templateData = templates.find(t => t.uuid === templateId);
                if (templateData) {
                  templateData["resourceType"] = "template";
                  const resourceDetails = new osparc.dashboard.ResourceDetails(templateData).set({
                    showOpenButton: false
                  });
                  osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
                }
              });
          });
        }
      });

      return templatesUIList;
    },

    __reloadOrgTemplates: function() {
      const templatesModel = this.__templatesModel;
      templatesModel.removeAll();

      const orgModel = this.__currentOrg;
      if (orgModel === null) {
        return;
      }

      const groupId = orgModel.getGroupId();
      osparc.data.Resources.getInstance().getAllPages("templates")
        .then(templates => {
          const orgTemplates = templates.filter(template => groupId in template["accessRights"]);
          orgTemplates.forEach(orgTemplate => {
            const orgTemplateCopy = osparc.utils.Utils.deepCloneObject(orgTemplate);
            orgTemplateCopy["orgId"] = groupId;
            templatesModel.append(qx.data.marshal.Json.createModel(orgTemplateCopy));
          });
        });
    }
  }
});
