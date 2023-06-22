/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.StudyMedium", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: 0,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    if (study instanceof osparc.data.model.Study) {
      this.setStudy(study);
    }

    this.addListenerOnce("appear", () => this.__rebuildLayout(), this);
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    }
  },

  members: {
    /**
      * @param studyData {Object} Serialized Study Object
      */
    setStudyData: function(studyData) {
      const study = new osparc.data.model.Study(studyData, false);
      this.setStudy(study);
    },

    checkResize: function(bounds) {
      this.__rebuildLayout(bounds.width);
    },

    __applyStudy: function() {
      this.__rebuildLayout();
    },

    __rebuildLayout: function(width) {
      this._removeAll();

      const nameAndMenuButton = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      nameAndMenuButton.add(this.__createTitle(), {
        flex: 1
      });
      nameAndMenuButton.add(this.__createMenuButton());
      this._add(nameAndMenuButton);

      const thumbnail = this.__createThumbnail(160, 100);
      if (thumbnail) {
        this._add(thumbnail);
      }

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);
      this._add(extraInfoLayout);

      const description = this.__createDescription();
      if (description) {
        this._add(description);
      }
    },

    __createMenuButton: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const menuButton = new qx.ui.form.MenuButton().set({
        menu,
        width: 25,
        height: 25,
        icon: "@FontAwesome5Solid/ellipsis-v/14",
        focusable: false
      });

      const moreInfoButton = this.__getMoreInfoMenuButton();
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      return menuButton;
    },

    __getMoreInfoMenuButton: function() {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        this.__openStudyDetails();
      }, this);
      return moreInfoButton;
    },

    __extraInfo: function() {
      const extraInfo = [{
        label: this.tr("AUTHOR"),
        view: this.__createOwner(),
        action: null
      }, {
        label: this.tr("ACCESS RIGHTS"),
        view: this.__createAccessRights()
      }, {
        label: this.tr("CREATED"),
        view: this.__createCreationDate(),
        action: null
      }, {
        label: this.tr("MODIFIED"),
        view: this.__createLastChangeDate(),
        action: null
      }, {
        label: this.tr("TAGS"),
        view: this.__createTags(),
        action: null
      }, {
        label: this.tr("DESCRIPTION"),
        view: this.__createDescription(),
        action: null
      }];

      if (
        osparc.product.Utils.showQuality() &&
        osparc.component.metadata.Quality.isEnabled(this.getStudy().getQuality())
      ) {
        extraInfo.push({
          label: this.tr("Quality"),
          view: this.__createQuality(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.__openQuality,
            ctx: this
          }
        });
      }
      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.info.StudyUtils.createExtraInfoVBox(extraInfo);

      return moreInfo;
    },

    __createTitle: function() {
      return osparc.info.StudyUtils.createTitle(this.getStudy());
    },

    __createOwner: function() {
      return osparc.info.StudyUtils.createOwner(this.getStudy());
    },

    __createCreationDate: function() {
      return osparc.info.StudyUtils.createCreationDate(this.getStudy());
    },

    __createLastChangeDate: function() {
      return osparc.info.StudyUtils.createLastChangeDate(this.getStudy());
    },

    __createAccessRights: function() {
      return osparc.info.StudyUtils.createAccessRights(this.getStudy());
    },

    __createQuality: function() {
      return osparc.info.StudyUtils.createQuality(this.getStudy());
    },

    __createThumbnail: function(maxWidth, maxHeight = 150) {
      if (this.getStudy().getThumbnail()) {
        return osparc.info.StudyUtils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
      }
      return null;
    },

    __createDescription: function() {
      if (this.getStudy().getDescription()) {
        const maxHeight = 300;
        return osparc.info.StudyUtils.createDescription(this.getStudy(), maxHeight);
      }
      return null;
    },

    __openAccessRights: function() {
      const permissionsView = osparc.info.StudyUtils.openAccessRights(this.getStudy().serialize());
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this.getStudy().setAccessRights(updatedData["accessRights"]);
      });
    },

    __openQuality: function() {
      const qualityEditor = osparc.info.StudyUtils.openQuality(this.getStudy().serialize());
      qualityEditor.addListener("updateQuality", e => {
        const updatedData = e.getData();
        this.getStudy().setQuality(updatedData["quality"]);
      });
    },

    __openStudyDetails: function() {
      const studyDetails = new osparc.info.StudyLarge(this.getStudy());
      const title = this.tr("Study Information");
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
    }
  }
});
