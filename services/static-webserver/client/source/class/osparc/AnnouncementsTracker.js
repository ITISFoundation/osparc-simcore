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

  statics: {
    CHECK_INTERVAL: 60*60*1000 // Check every 60'
  },

  members: {
    __checkInternval: null,
    __announcements: null,

    startTracker: function() {
      const fakeAnnouncements = [{
        "id": "Student_Competition_2023",
        "products": ["s4llite"],
        "start": "2023-06-22T15:00:00.000Z",
        "end": "2023-11-01T02:00:00.000Z",
        "title": "Student Competition 2023",
        "description": "For more information click <a href='https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/' style='color: white' target='_blank'>here</a>",
        "link": "https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/",
        "widgets": ["login", "ribbon"]
      },
      {
        "id": "TIP_v2",
        "products": ["tis"],
        "start": "2023-07-10T15:00:00.000Z",
        "end": "2023-08-01T02:00:00.000Z",
        "title": "TIP v2",
        "description": "For more information click <a href='https://itis.swiss/tools-and-systems/ti-planning/' style='color: white' target='_blank'>here</a>",
        "link": "https://itis.swiss/tools-and-systems/ti-planning/",
        "widgets": ["login", "ribbon", "user-menu"]
      }];
      const checkAnnouncements = () => {
        this.__setAnnouncements(fakeAnnouncements);
        osparc.data.Resources.get("announcements")
          .then(announcements => {
            if (announcements && announcements.length) {
              this.__setAnnouncements([JSON.parse(announcements)]);
            } else {
              this.__setAnnouncements(null);
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

    __setAnnouncements: function(announcementsData) {
      this.__announcements = {};
      if (announcementsData) {
        announcementsData.forEach(announcementData => {
          const announcement = new osparc.component.announcement.Announcement(announcementData);
          osparc.component.announcement.AnnouncementUIFactory.getInstance().setAnnouncement(announcement);
        });
      }
    }
  }
});
