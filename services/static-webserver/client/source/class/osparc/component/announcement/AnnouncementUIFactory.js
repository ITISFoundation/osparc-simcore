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

qx.Class.define("osparc.component.announcement.AnnouncementUIFactory", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    announcement: {
      check: "osparc.component.announcement.Announcement",
      init: null,
      nullable: false,
      apply: "__buildAnnouncementUIs"
    },

    loginAnnouncement: {
      check: "qx.ui.core.Widget",
      init: null,
      nullable: true,
      event: "changeLoginAnnouncement"
    },

    ribbonAnnouncement: {
      check: "qx.ui.core.Widget",
      init: null,
      nullable: true,
      event: "changeRibbonAnnouncement"
    },

    userMenuAnnouncement: {
      check: "qx.ui.core.Widget",
      init: null,
      nullable: true,
      event: "changeUserMenuAnnouncement"
    }
  },

  members: {
    __buildAnnouncementUIs: function() {
      if (this.__isValid()) {
        this.__buildLoginAnnouncement();
        this.__buildUserMenuAnnouncement();
      } else {
        this.setLoginAnnouncement(null);
        this.setRibbonAnnouncement(null);
        this.setUserMenuAnnouncement(null);
      }
    },

    __isValid: function() {
      const announcement = this.getAnnouncement();

      const now = new Date();
      if (
        announcement.getProducts().includes(osparc.product.Utils.getProductName()) &&
        now > announcement.getStart() &&
        now < announcement.getEnd()
      ) {
        return true;
      }
      return false;
    },

    __buildLoginAnnouncement: function() {
      const announcement = this.getAnnouncement();

      const loginAnnouncement = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        backgroundColor: "strong-main",
        alignX: "center",
        padding: 12,
        allowGrowX: true,
        maxWidth: 300
      });
      loginAnnouncement.getContentElement().setStyles({
        "border-radius": "8px"
      });

      const titleLabel = new qx.ui.basic.Label().set({
        value: announcement.getTitle(),
        font: "text-16",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      loginAnnouncement.add(titleLabel);

      const descriptionLabel = new qx.ui.basic.Label().set({
        value: announcement.getDescription(),
        font: "text-14",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      loginAnnouncement.add(descriptionLabel);

      this.setLoginAnnouncement(loginAnnouncement);
    },

    __buildUserMenuAnnouncement: function() {
      const announcement = this.getAnnouncement();

      const link = announcement.getLink();
      if (link) {
        const userMenuAnnouncement = new qx.ui.menu.Button(announcement.getTitle() + "...");
        userMenuAnnouncement.addListener("execute", () => window.open(link));

        this.setUserMenuAnnouncement(userMenuAnnouncement);
      } else {
        this.setUserMenuAnnouncement(null);
      }
    }
  }
});
