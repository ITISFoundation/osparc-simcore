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

qx.Class.define("osparc.AnnouncementTracker", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    start: {
      check: "Date",
      init: null,
      nullable: true
    },

    end: {
      check: "Date",
      init: null,
      nullable: true
    },

    title: {
      check: "String",
      init: null,
      nullable: true
    },

    description: {
      check: "String",
      init: null,
      nullable: true
    }
  },

  members: {
    __loginAnnouncement: null,

    startTracker: function() {
      if (osparc.product.Utils.isProduct("s4llite")) {
        const announcementData = {
          start: "2023-06-22T15:00:00.000Z",
          end: "2023-11-01T02:00:00.000Z",
          title: "Student Competition 2023",
          description: "For more information click <a href='https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/'  style='color: white' target='_blank'>here</a>"
        };
        this.__setAnnouncement(announcementData);
      }
    },

    getLoginAnnouncement: function() {
      const now = new Date();
      if (
        this.__loginAnnouncement &&
        this.getStart() > now &&
        now < this.getEnd()
      ) {
        return this.__loginAnnouncement;
      }
      return null;
    },

    __setAnnouncement: function(announcementData) {
      this.setStart(announcementData && "start" in announcementData ? new Date(announcementData.start) : null);
      this.setEnd(announcementData && "end" in announcementData ? new Date(announcementData.end) : null);
      this.setTitle(announcementData && "title" in announcementData ? announcementData.title : null);
      this.setDescription(announcementData && "description" in announcementData ? announcementData.description : null);

      this.__buildAnnouncementUIs();
    },

    __buildAnnouncementUIs: function() {
      this.__buildLoginAnnouncement();
      this.__buildUserMenuAnnouncement();
    },

    __buildLoginAnnouncement: function() {
      const announcmentLayout = this.__loginAnnouncement = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        backgroundColor: "strong-main",
        alignX: "center",
        padding: 12,
        allowGrowX: true,
        maxWidth: 300
      });
      announcmentLayout.getContentElement().setStyles({
        "border-radius": "8px"
      });

      const titleLabel = new qx.ui.basic.Label().set({
        value: this.getTitle(),
        font: "text-16",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      announcmentLayout.add(titleLabel);

      const descriptionLabel = new qx.ui.basic.Label().set({
        value: this.getDescription(),
        font: "text-14",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      announcmentLayout.add(descriptionLabel);
    },

    __buildUserMenuAnnouncement: function() {
    }
  }
});
