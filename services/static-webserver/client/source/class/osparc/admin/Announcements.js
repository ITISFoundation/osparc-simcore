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

qx.Class.define("osparc.admin.Announcements", {
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "create-announcement":
          control = this.__createAnnouncements();
          this._add(control);
          break;
        case "announcement-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("create-announcement");
      this.getChildControl("announcement-container");
    },

    __createAnnouncements: function() {
      const announcementGroupBox = osparc.po.BaseView.createGroupBox(this.tr("Create announcement"));

      const announcementForm = this.__createAnnouncementForm();
      const form = new qx.ui.form.renderer.Single(announcementForm);
      announcementGroupBox.add(form);

      return announcementGroupBox;
    },

    __createAnnouncementForm: function() {
      const form = new qx.ui.form.Form();

      const title = new qx.ui.form.TextField().set({
        placeholder: this.tr("title")
      });
      form.add(title, this.tr("Title"));

      const description = new qx.ui.form.TextArea().set({
        placeholder: this.tr("description"),
        maxHeight: 60
      });
      form.add(description, this.tr("Description"));

      const link = new qx.ui.form.TextField().set({
        placeholder: this.tr("link")
      });
      form.add(link, this.tr("Link"));

      const widgetLogin = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(widgetLogin, this.tr("Login"));

      const widgetRibbon = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(widgetRibbon, this.tr("Ribbon"));

      const widgetUserMenu = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(widgetUserMenu, this.tr("User Menu"));

      const dateFormat = new qx.util.format.DateFormat("dd/MM/yyyy");
      const now = new Date();

      const start = new qx.ui.form.DateField();
      start.setDateFormat(dateFormat);
      start.setValue(now);
      form.add(start, this.tr("Start"));

      const end = new qx.ui.form.DateField();
      end.setDateFormat(dateFormat);
      end.setValue(now);
      form.add(end, this.tr("End"));

      const generateAnnouncementBtn = new osparc.ui.form.FetchButton(this.tr("Generate"));
      generateAnnouncementBtn.set({appearance: "form-button"});
      generateAnnouncementBtn.addListener("execute", () => {
        const products = [osparc.product.Utils.getProductName()];
        const widgets = [];
        if (widgetLogin.getValue()) {
          widgets.push("login");
        }
        if (widgetRibbon.getValue()) {
          widgets.push("ribbon");
        }
        if (widgetUserMenu.getValue()) {
          widgets.push("user-menu");
        }
        if (widgets.length === 0) {
          const msg = "Select at least one widget";
          osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
        }
        const announcementData = {
          "id": osparc.utils.Utils.uuidV4(),
          "products": products,
          "title": title.getValue() ? title.getValue() : "",
          "description": description.getValue() ? description.getValue() : "",
          "link": link.getValue() ? link.getValue() : "",
          "widgets": widgets,
          "start": start.getValue(),
          "end": end.getValue(),
        };
        this.__populateAnnouncementLayout(announcementData);
      }, this);
      form.addButton(generateAnnouncementBtn);

      return form;
    },

    __populateAnnouncementLayout: function(announcementData) {
      const vBox = this.getChildControl("announcement-container");
      vBox.removeAll();

      const announcementField = new qx.ui.form.TextArea(JSON.stringify(announcementData)).set({
        readOnly: true
      });
      vBox.add(announcementField);

      const copyAnnouncementBtn = new qx.ui.form.Button(this.tr("Copy announcement")).set({
        alignX: "left",
        allowGrowX: false,
      });
      copyAnnouncementBtn.set({appearance: "form-button"});
      copyAnnouncementBtn.addListener("execute", () => {
        if (osparc.utils.Utils.copyTextToClipboard(JSON.stringify(announcementData))) {
          copyAnnouncementBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      vBox.add(copyAnnouncementBtn);
    },
  }
});
