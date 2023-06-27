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

qx.Class.define("osparc.AnnouncementsTracker", {
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
    },

    link: {
      check: "String",
      init: null,
      nullable: true
    }
  },

  statics: {
    CHECK_INTERVAL: 60*60*1000 // Check every 60'
  },

  members: {
    __checkInternval: null,
    __loginAnnouncement: null,
    __userMenuAnnouncement: null,

    startTracker: function() {
      /*
      if (osparc.product.Utils.isProduct("s4llite")) {
        const announcementData = {
          start: "2023-06-22T15:00:00.000Z",
          end: "2023-11-01T02:00:00.000Z",
          title: "Student Competition 2023",
          description: "For more information click <a href='https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/' style='color: white' target='_blank'>here</a>",
          link: "https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/"
        };
        this.__setAnnouncement(announcementData);
      }
      */
      const checkAnnouncements = () => {
        osparc.data.Resources.get("announcements")
          .then(announcements => {
            console.log("announcements", announcements);
            if (announcements) {
              // for now it's just a string
              this.__setAnnouncement(JSON.parse(announcements));
            } else {
              this.__setMaintenance(null);
            }
          })
          .catch(err => console.error(err));
      };
      checkAnnouncements();
      this.__checkInternval = setInterval(checkAnnouncements, this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInternval) {
        clearInterval(this.__checkInternval);
      }
    },

    getLoginAnnouncement: function() {
      if (this.__isValid() && this.__loginAnnouncement) {
        return this.__loginAnnouncement;
      }
      return null;
    },

    getUserMenuAnnouncement: function() {
      if (this.__isValid() && this.__userMenuAnnouncement) {
        return this.__userMenuAnnouncement;
      }
      return null;
    },

    __isValid: function() {
      const now = new Date();
      if (
        this.getStart() &&
        this.getEnd() &&
        now > this.getStart() &&
        now < this.getEnd()
      ) {
        return true;
      }
      return false;
    },

    __setAnnouncement: function(announcementData) {
      this.setStart(announcementData && "start" in announcementData ? new Date(announcementData.start) : null);
      this.setEnd(announcementData && "end" in announcementData ? new Date(announcementData.end) : null);
      this.setTitle(announcementData && "title" in announcementData ? announcementData.title : null);
      this.setDescription(announcementData && "description" in announcementData ? announcementData.description : null);
      this.setLink(announcementData && "link" in announcementData ? announcementData.link : null);

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
      const link = this.getLink();
      if (link) {
        const button = this.__userMenuAnnouncement = new qx.ui.menu.Button(this.getTitle() + "...");
        button.addListener("execute", () => window.open(link));
      }
    }
  }
});
