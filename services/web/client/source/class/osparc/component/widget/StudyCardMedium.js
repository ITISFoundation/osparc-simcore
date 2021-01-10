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


qx.Class.define("osparc.component.widget.StudyCardMedium", {
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

    if (study) {
      if (study instanceof osparc.data.model.Study) {
        this.setStudy(study);
      } else {
        this.setStudyData(study);
      }
    }
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    },

    slim: {
      check: "Boolean",
      apply: "__rebuildLayout",
      init: null,
      nullable: false
    }
  },

  statics: {
    PADDING: 10,
    EXTRA_INFO_WIDTH: 200,
    THUMBNAIL_MIN_WIDTH: 120
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
      const slim = bounds.width < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING;
      this.setSlim(slim);
    },

    __applyStudy: function() {
      this.__rebuildLayout();
    },

    __rebuildLayout: function() {
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
      const widgetWidth = this.getBounds() ? this.getBounds().width : 350;
      const thumbnailWidth = widgetWidth - 2*this.self().PADDING - this.self().EXTRA_INFO_WIDTH;
      const thumbnail = this.__createThumbnail(thumbnailWidth);
      if (this.getSlim() === null || this.getSlim() === false) {
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center",
          alignY: "middle"
        }));
        hBox.add(extraInfo);
        hBox.add(thumbnail, {
          flex: 1
        });
        this._add(hBox);
      } else {
        this._add(extraInfo);
        this._add(thumbnail);
      }

      this._add(this.__createDescription(), {
        flex: 1
      });
    },

    __createTitle: function() {
      const title = new qx.ui.basic.Label().set({
        font: "title-14",
        allowStretchX: true,
        rich: true
      });
      this.getStudy().bind("name", title, "value");
      return title;
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

      if (this.getStudy().getQuality()) {
        const qualityButton = this.__getQualityMenuButton();
        menu.add(qualityButton);
      }

      return menuButton;
    },

    __getMoreInfoMenuButton: function() {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        this.__openStudyDetailsEditor();
      }, this);
      return moreInfoButton;
    },

    __getQualityMenuButton: function() {
      const studyQualityButton = new qx.ui.menu.Button(this.tr("Quality"));
      studyQualityButton.addListener("execute", () => {
      }, this);
      return studyQualityButton;
    },

    __extraInfo: function() {
      const grid = new qx.ui.layout.Grid(5, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnFlex(1, 1);
      const moreInfo = new qx.ui.container.Composite(grid).set({
        width: this.self().EXTRA_INFO_WIDTH,
        alignX: "center",
        alignY: "middle"
      });

      let row = 0;
      const owner = this.__createOwner();
      moreInfo.add(new qx.ui.basic.Label(this.tr("Owner")).set({
        font: "title-12"
      }), {
        row,
        column: 0
      });
      moreInfo.add(owner, {
        row,
        column: 1
      });
      row++;

      const creationDate = this.__createCreationDate();
      moreInfo.add(new qx.ui.basic.Label(this.tr("Creation date")).set({
        font: "title-12"
      }), {
        row,
        column: 0
      });
      moreInfo.add(creationDate, {
        row,
        column: 1
      });
      row++;

      const lastChangeDate = this.__createLastChangeDate();
      moreInfo.add(new qx.ui.basic.Label(this.tr("Last modified")).set({
        font: "title-12"
      }), {
        row,
        column: 0
      });
      moreInfo.add(lastChangeDate, {
        row,
        column: 1
      });
      row++;

      const accessRights = this.__createAccessRights();
      moreInfo.add(new qx.ui.basic.Label(this.tr("Access rights")).set({
        font: "title-12"
      }), {
        row,
        column: 0
      });
      moreInfo.add(accessRights, {
        row,
        column: 1
      });
      row++;

      const quality = this.__createQuality();
      if (quality) {
        moreInfo.add(new qx.ui.basic.Label(this.tr("Quality")).set({
          font: "title-12"
        }), {
          row,
          column: 0
        });
        moreInfo.add(quality, {
          row,
          column: 1
        });
        row++;
      }

      return moreInfo;
    },

    __createOwner: function() {
      const owner = new qx.ui.basic.Label();
      this.getStudy().bind("prjOwner", owner, "value", {
        converter: email => osparc.utils.Utils.getNameFromEmail(email),
        onUpdate: (source, target) => {
          target.setToolTipText(source.getPrjOwner());
        }
      });
      return owner;
    },

    __createCreationDate: function() {
      // create a date format like "Oct. 19, 2018 11:31 AM"
      const dateFormat = new qx.util.format.DateFormat(
        qx.locale.Date.getDateFormat("medium") + " " +
        qx.locale.Date.getTimeFormat("short")
      );
      const dateOptions = {
        converter: date => dateFormat.format(date)
      };
      const creationDate = new qx.ui.basic.Label();
      this.getStudy().bind("creationDate", creationDate, "value", dateOptions);
      return creationDate;
    },

    __createLastChangeDate: function() {
      // create a date format like "Oct. 19, 2018 11:31 AM"
      const dateFormat = new qx.util.format.DateFormat(
        qx.locale.Date.getDateFormat("medium") + " " +
        qx.locale.Date.getTimeFormat("short")
      );
      const dateOptions = {
        converter: date => dateFormat.format(date)
      };
      const lastChangeDate = new qx.ui.basic.Label();
      this.getStudy().bind("lastChangeDate", lastChangeDate, "value", dateOptions);
      return lastChangeDate;
    },

    __createAccessRights: function() {
      const accessRights = new qx.ui.basic.Label(this.tr("Collaborator"));

      this.getStudy().addListener("changeAccessRights", e => {
        console.log("changeAccessRights", e.getData());
      });

      return accessRights;
    },

    __createQuality: function() {
      const quality = this.getStudy().getQuality();
      if (quality && "tsr" in quality) {
        const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
          toolTipText: this.tr("Ten Simple Rules score")
        });
        const {
          score,
          maxScore
        } = osparc.component.metadata.Quality.computeTSRScore(quality["tsr"]);
        const tsrRating = new osparc.ui.basic.StarsRating();
        tsrRating.set({
          score,
          maxScore,
          nStars: 4,
          showScore: true
        });
        tsrLayout.add(tsrRating);

        this.getStudy().addListener("changeQuality", e => {
          console.log("changeQuality", e.getData());
        });

        return tsrLayout;
      }
      return null;
    },

    __createThumbnail: function(maxWidth) {
      const maxHeight = 250;
      const image = new osparc.component.widget.Thumbnail(null, maxWidth, maxHeight);
      const img = image.getChildControl("image");
      this.getStudy().bind("thumbnail", img, "source");
      this.getStudy().bind("thumbnail", img, "visibility", {
        converter: thumbnail => {
          if (thumbnail) {
            return "visible";
          }
          return "excluded";
        }
      });
      return image;
    },

    __createDescription: function() {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: false,
        maxHeight: 300
      });
      this.getStudy().bind("description", description, "value");
      return description;
    },

    __openStudyDetailsEditor: function() {
      const width = 500;
      const height = 500;
      const title = this.tr("Study Details Editor");
      const studyDetailsEditor = new osparc.component.metadata.StudyDetailsEditor(this.getStudy().serialize(), false, width)
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
