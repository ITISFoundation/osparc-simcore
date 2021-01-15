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


qx.Class.define("osparc.studycard.Utils", {
  type: "static",

  statics: {
    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createTitle: function(study) {
      const title = new qx.ui.basic.Label().set({
        font: "title-14",
        allowStretchX: true,
        rich: true
      });
      if (study instanceof osparc.data.model.Study) {
        study.bind("name", title, "value");
      } else {
        title.setValue(study["name"]);
      }
      return title;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createUuid: function(study) {
      const uuid = new qx.ui.basic.Label().set({
        maxWidth: 150
      });
      if (study instanceof osparc.data.model.Study) {
        study.bind("uuid", uuid, "value");
        study.bind("uuid", uuid, "toolTipText");
      } else {
        uuid.set({
          value: study["uuid"],
          toolTipText: study["uuid"]
        });
      }
      return uuid;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createOwner: function(study) {
      const owner = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
        study.bind("prjOwner", owner, "value", {
          converter: email => osparc.utils.Utils.getNameFromEmail(email),
          onUpdate: (source, target) => {
            target.setToolTipText(source.getPrjOwner());
          }
        });
      } else {
        owner.set({
          value: osparc.utils.Utils.getNameFromEmail(study["prjOwner"]),
          toolTipText: study["prjOwner"]
        });
      }
      return owner;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createCreationDate: function(study) {
      const creationDate = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
        const dateOptions = {
          converter: date => osparc.utils.Utils.formatDateAndTime(date)
        };
        study.bind("creationDate", creationDate, "value", dateOptions);
      } else {
        const date = osparc.utils.Utils.formatDateAndTime(new Date(study["creationDate"]));
        creationDate.setValue(date);
      }
      return creationDate;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createLastChangeDate: function(study) {
      const lastChangeDate = new qx.ui.basic.Label();
      if (study instanceof osparc.data.model.Study) {
        const dateOptions = {
          converter: date => osparc.utils.Utils.formatDateAndTime(date)
        };
        study.bind("lastChangeDate", lastChangeDate, "value", dateOptions);
      } else {
        const date = osparc.utils.Utils.formatDateAndTime(new Date(study["lastChangeDate"]));
        lastChangeDate.setValue(date);
      }
      return lastChangeDate;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createAccessRights: function(study) {
      let permissions = "";
      const myGID = osparc.auth.Data.getInstance().getGroupId();
      const ar = (study instanceof osparc.data.model.Study) ? study.getAccessRights() : study["accessRights"];
      if (myGID in ar) {
        if (ar[myGID]["delete"]) {
          permissions = qx.locale.Manager.tr("Owner");
        } else if (ar[myGID]["write"]) {
          permissions = qx.locale.Manager.tr("Collaborator");
        } else if (ar[myGID]["read"]) {
          permissions = qx.locale.Manager.tr("Viewer");
        }
      }
      const accessRights = new qx.ui.basic.Label(permissions);
      return accessRights;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      */
    createQuality: function(study) {
      const quality = (study instanceof osparc.data.model.Study) ? study.getQuality() : study["quality"];
      if (quality && "tsr" in quality) {
        const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
          toolTipText: qx.locale.Manager.tr("Ten Simple Rules score")
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

        return tsrLayout;
      }
      return null;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      * @param maxWidth {Number} thumbnail's maxWidth
      * @param maxHeight {Number} thumbnail's maxHeight
      */
    createThumbnail: function(study, maxWidth) {
      const maxHeight = 160;
      const image = new osparc.component.widget.Thumbnail(null, maxWidth, maxHeight);
      const img = image.getChildControl("image");
      if (study instanceof osparc.data.model.Study) {
        study.bind("thumbnail", img, "source", {
          converter: thumbnail => thumbnail === "" ? osparc.dashboard.StudyBrowserButtonItem.STUDY_ICON : thumbnail
        });
      } else {
        img.set({
          source: study["thumbnail"] === "" ? osparc.dashboard.StudyBrowserButtonItem.STUDY_ICON : study["thumbnail"]
        });
      }
      return image;
    },

    /**
      * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
      * @param maxHeight {Number} description's maxHeight
      */
    createDescription: function(study, maxHeight) {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: false,
        maxHeight: maxHeight
      });
      if (study instanceof osparc.data.model.Study) {
        study.bind("description", description, "value");
      } else {
        description.setValue(study["description"]);
      }
      return description;
    },

    /**
      * @param studyData {Object} Serialized Study Object
      */
    createTags: function(studyData) {
      const tagsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Tags")).set({
        font: "title-12"
      });
      tagsLayout.add(label);

      const tagsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      tagsContainer.setMarginTop(5);
      osparc.store.Store.getInstance().getTags().filter(tag => studyData.tags.includes(tag.id))
        .forEach(selectedTag => {
          tagsContainer.add(new osparc.ui.basic.Tag(selectedTag.name, selectedTag.color));
        });
      tagsLayout.add(tagsContainer);

      return tagsLayout;
    },

    /**
      * @param studyData {Object} Serialized Study Object
      */
    createClassifiers: function(studyData) {
      const classfiersLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      const label = new qx.ui.basic.Label(qx.locale.Manager.tr("Classifiers")).set({
        font: "title-12"
      });
      classfiersLayout.add(label);

      const classifiersContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      studyData["classifiers"].forEach(classifier => {
        classifiersContainer.add(new qx.ui.basic.Label(classifier));
      });
      classfiersLayout.add(classifiersContainer);

      return classfiersLayout;
    },

    /**
      * @param studyData {Object} Serialized Study Object
      */
    openAccessRights: function(studyData) {
      const permissionsView = new osparc.component.export.StudyPermissions(studyData);
      const title = qx.locale.Manager.tr("Share with Collaborators and Organizations");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      return permissionsView;
    },

    /**
      * @param studyData {Object} Serialized Study Object
      */
    openQuality: function(studyData) {
      const qualityEditor = new osparc.component.metadata.QualityEditor(studyData);
      const title = studyData["name"] + " - " + qx.locale.Manager.tr("Quality Assessment");
      osparc.ui.window.Window.popUpInWindow(qualityEditor, title, 650, 760);
      return qualityEditor;
    }
  }
});
