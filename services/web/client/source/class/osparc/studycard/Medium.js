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


qx.Class.define("osparc.studycard.Medium", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: this.self().PADDING,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(3));

    if (study && study instanceof osparc.data.model.Study) {
      this.setStudy(study);
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    }
  },

  statics: {
    PADDING: 10,
    EXTRA_INFO_WIDTH: 200,
    THUMBNAIL_MIN_WIDTH: 120,
    THUMBNAIL_MAX_WIDTH: 200
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

      const nameAndMenuButton = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      }));
      nameAndMenuButton.add(this.__createTitle(), {
        flex: 1
      });
      nameAndMenuButton.add(this.__createMenuButton());
      this._add(nameAndMenuButton);

      const extraInfo = this.__extraInfo();

      const bounds = this.getBounds();
      let widgetWidth = null;
      if (width) {
        widgetWidth = width;
      } else if (bounds) {
        widgetWidth = bounds.width;
      } else {
        widgetWidth = 350;
      }
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING;
      const slim = widgetWidth < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING;
      if (slim) {
        thumbnailWidth = Math.min(thumbnailWidth, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth);
        this._add(extraInfo);
        this._add(thumbnail);
      } else {
        thumbnailWidth -= this.self().EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth);
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center",
          alignY: "middle"
        }));
        hBox.add(extraInfo);
        hBox.add(thumbnail, {
          flex: 1
        });
        this._add(hBox);
      }

      this._add(this.__createDescription());
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
        this.__openStudyCardLarge();
      }, this);
      return moreInfoButton;
    },

    __extraInfo: function() {
      const grid = new qx.ui.layout.Grid(5, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid).set({
        width: this.self().EXTRA_INFO_WIDTH,
        alignX: "center",
        alignY: "middle"
      });

      const extraInfo = [
        [this.tr("Author"), this.__createOwner()],
        [this.tr("Creation date"), this.__createCreationDate()],
        [this.tr("Last modified"), this.__createLastChangeDate()],
        [this.tr("Access rights"), this.__createAccessRights()],
        [this.tr("Quality"), this.__createQuality()]
      ];
      for (let i=0; i<extraInfo.length; i++) {
        if (extraInfo[i][1]) {
          moreInfo.add(new qx.ui.basic.Label(extraInfo[i][0]).set({
            font: "title-12"
          }), {
            row: i,
            column: 0
          });

          moreInfo.add(extraInfo[i][1], {
            row: i,
            column: 1
          });
        }
      }

      return moreInfo;
    },

    __createTitle: function() {
      return osparc.studycard.Utils.createTitle(this.getStudy());
    },

    __createOwner: function() {
      return osparc.studycard.Utils.createOwner(this.getStudy());
    },

    __createCreationDate: function() {
      return osparc.studycard.Utils.createCreationDate(this.getStudy());
    },

    __createLastChangeDate: function() {
      return osparc.studycard.Utils.createLastChangeDate(this.getStudy());
    },

    __createAccessRights: function() {
      return osparc.studycard.Utils.createAccessRights(this.getStudy());
    },

    __createQuality: function() {
      return osparc.studycard.Utils.createQuality(this.getStudy());
    },

    __createThumbnail: function(maxWidth) {
      const maxHeight = 150;
      return osparc.studycard.Utils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 300;
      return osparc.studycard.Utils.createDescription(this.getStudy(), maxHeight);
    },

    __openStudyCardLarge: function() {
      const width = 500;
      const height = 500;
      const title = this.tr("Study Details Editor");
      const studyDetailsEditor = new osparc.component.metadata.StudyDetailsEditor(this.getStudy().serialize(), false, width);
      studyDetailsEditor.showOpenButton(false);
      const win = osparc.ui.window.Window.popUpInWindow(studyDetailsEditor, title, width, height);
      studyDetailsEditor.addListener("updateStudy", e => {
        const newStudyData = e.getData();
        this.getStudy().set({
          name: newStudyData.name,
          description: newStudyData.description,
          thumbnail: newStudyData.thumbnail
        });
        qx.event.message.Bus.getInstance().dispatchByName("updateStudy", newStudyData.uuid);
        win.close();
      });
    }
  }
});
