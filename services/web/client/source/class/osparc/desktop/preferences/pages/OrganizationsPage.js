/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Organization and members in preferences dialog
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.OrganizationsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/sitemap/24";
    const title = this.tr("Organizations");
    this.base(arguments, title, iconSrc);


    this.add(this.__createOrganizations());
    this.add(this.__createMembers());
  },

  members: {
    __createOrganizations: function() {
      const box = this._createSectionBox(this.tr("Organizations"));

      const orgsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150
      });
      box.add(orgsUIList);

      const orgsModel = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(orgsModel, orgsUIList, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.component.widget.OrganizationListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "gid", null, item, id);
          ctrl.bindProperty("label", "label", null, item, id);
          ctrl.bindProperty("description", "description", null, item, id);
        }
      });

      const store = osparc.store.Store.getInstance();
      store.getGroupsOrganizations()
        .then(orgs => {
          orgsModel.removeAll();
          orgs.forEach(org => orgsModel.append(qx.data.marshal.Json.createModel(org)));
        });

      return box;
    },

    __createMembers: function() {
      const box = this._createSectionBox(this.tr("Members"));

      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));
      box.add(container);

      container.add(new qx.ui.basic.Label(this.tr("Select organization")));

      const orgsBox = new qx.ui.form.SelectBox();
      orgsBox.add(new qx.ui.form.ListItem(""));

      const store = osparc.store.Store.getInstance();
      store.getGroupsOrganizations()
        .then(orgs => {
          orgs.forEach(org => {
            orgsBox.add(new qx.ui.form.ListItem(org.label));
          });
        });

      container.add(orgsBox);

      const membersUIList = new qx.ui.form.List().set({
        spacing: 3,
        height: 150,
        width: 150
      });
      box.add(membersUIList);

      return box;
    }
  }
});
