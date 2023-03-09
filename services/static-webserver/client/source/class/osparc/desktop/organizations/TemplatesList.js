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
      const filter = new osparc.component.filter.TextFilter("text", "organizationTemplatesList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getTemplatesList: function() {
      const templatesUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        backgroundColor: "background-main-2"
      });

      const templatesModel = this.__templatesModel = new qx.data.Array();
      const templatesCtrl = new qx.data.controller.List(templatesModel, templatesUIList, "name");
      templatesCtrl.setDelegate({
        createItem: () => new osparc.ui.list.ListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("uuid", "model", null, item, id);
          ctrl.bindProperty("uuid", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitleMD", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationTemplatesList");
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

      osparc.data.Resources.getInstance().getAllPages("templates")
        .then(templates => {
          const gid = orgModel.getGid();
          const orgTemplates = templates.filter(template => gid in template["accessRights"]);
          orgTemplates.forEach(orgTemplate => templatesModel.append(qx.data.marshal.Json.createModel(orgTemplate)));
        });
    }
  }
});
