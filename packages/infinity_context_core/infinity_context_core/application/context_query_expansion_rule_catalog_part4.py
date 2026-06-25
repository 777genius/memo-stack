"""Static query expansion rule catalog part 4."""

from __future__ import annotations

from infinity_context_core.application import context_query_expansion_rule_terms as _terms

_EXERCISE_ACTIVITY_EXPANSION = (
    "exercise exercises workout workouts kickboxing taekwondo yoga weight "
    "training circuit training strength flexibility agility speed shooting "
    "accuracy stamina endurance boxing sprinting running stay shape fitness energy "
    "basketball performance game court"
)

EXPANSION_RULES_PART_4: tuple[tuple[frozenset[str], str, str], ...] = (
    (
            frozenset({"artist", "seen"}),
            (
                "musical artists bands saw seen live concert show festival performance "
                "performed summer sounds band pop dancing singing lively fun"
            ),
            "music_artist_band_bridge",
        ),
    (
            frozenset({"band", "seen"}),
            (
                "musical artists bands saw seen live concert show festival performance "
                "performed summer sounds band pop dancing singing lively fun"
            ),
            "music_artist_band_bridge",
        ),
    (
            frozenset({"artist", "band"}),
            "matt patterson talented voice amazing singer named performer artist",
            "music_artist_answer_bridge",
        ),
    (
            frozenset({"artist", "seen"}),
            "matt patterson talented voice amazing singer named performer artist",
            "music_artist_answer_bridge",
        ),
    (
            frozenset({"band", "seen"}),
            "matt patterson talented voice amazing singer named performer artist",
            "music_artist_answer_bridge",
        ),
    (
            frozenset({"shoe", "used"}),
            ("new shoes purple walking running used for walk run love color sneakers"),
            "shoe_usage_bridge",
        ),
    (
            frozenset({"both", "common"}),
            (
                "both common shared mutual lost job lost jobs own business start "
                "starting own business dance studio clothing store store business "
                "banker door dash job loss launched ad campaign"
            ),
            "business_commonality_bridge",
        ),
    (
            frozenset({"common"}),
            (
                "both common shared mutual lost job lost jobs own business start "
                "starting own business dance studio clothing store store business "
                "banker door dash job loss launched ad campaign"
            ),
            "business_commonality_bridge",
        ),
    (
            frozenset({"martial"}),
            (
                "martial arts kickboxing taekwondo boxing karate workout class "
                "exercise exercises fitness energy stay shape de-stress "
                "doing kickboxing giving energy off to do some taekwondo"
            ),
            "exercise_activity_inventory_bridge",
        ),
    (
            frozenset({"exercise"}),
            _EXERCISE_ACTIVITY_EXPANSION,
            "exercise_activity_inventory_bridge",
        ),
    (
            frozenset({"exercises"}),
            _EXERCISE_ACTIVITY_EXPANSION,
            "exercise_activity_inventory_bridge",
        ),
    (
            frozenset({"workout"}),
            _EXERCISE_ACTIVITY_EXPANSION,
            "exercise_activity_inventory_bridge",
        ),
    (
            frozenset({"workouts"}),
            _EXERCISE_ACTIVITY_EXPANSION,
            "exercise_activity_inventory_bridge",
        ),
    (
            frozenset({"reason", "running"}),
            _terms._RUNNING_REASON_EXPANSION,
            "running_reason_bridge",
        ),
    (
            frozenset({"reason", "running"}),
            _terms._RUNNING_REASON_QUESTION_EXPANSION,
            "running_reason_question_bridge",
        ),
    (
            frozenset({"getting", "running"}),
            _terms._RUNNING_REASON_EXPANSION,
            "running_reason_bridge",
        ),
    (
            frozenset({"getting", "running"}),
            _terms._RUNNING_REASON_QUESTION_EXPANSION,
            "running_reason_question_bridge",
        ),
    (
            frozenset({"start", "running"}),
            _terms._RUNNING_REASON_EXPANSION,
            "running_reason_bridge",
        ),
    (
            frozenset({"start", "running"}),
            _terms._RUNNING_REASON_QUESTION_EXPANSION,
            "running_reason_question_bridge",
        ),
    (
            frozenset({"running", "for"}),
            _terms._RUNNING_REASON_EXPANSION,
            "running_reason_bridge",
        ),
    (
            frozenset({"running", "for"}),
            _terms._RUNNING_REASON_QUESTION_EXPANSION,
            "running_reason_question_bridge",
        ),
    (
            frozenset({"meteor", "shower", "feel"}),
            ("meteor shower felt tiny awe universe awesome life sky stars watching camping trip"),
            "meteor_shower_feeling_bridge",
        ),
    (
            frozenset({"feel"}),
            (
                "felt feel feeling emotion reaction after event accident roadtrip "
                "family grateful thankful relieved lucky okay scared freaked bad "
                "start means world mean world need them need family loved ones "
                "cherish family everything important love support gratitude "
                "inspired proud happy sad upset because reason"
            ),
            "post_event_emotion_bridge",
        ),
    (
            frozenset({"color", "pattern", "pottery"}),
            (
                "pottery colors patterns catch eye make people smile express feelings "
                "creative creativity painting stroke project"
            ),
            "pottery_color_reason_bridge",
        ),
    (
            frozenset({"pottery", "type"}),
            (
                "pottery types pieces made clay finished ceramic bowl bowls cup mug "
                "painted intricate design project another class kids creativity imagination"
            ),
            "pottery_type_bridge",
        ),
    (
            frozenset({"pottery", "made"}),
            (
                "pottery types pieces made clay finished ceramic bowl bowls cup mug "
                "painted intricate design project another class kids creativity imagination"
            ),
            "pottery_type_bridge",
        ),
    (
            frozenset({"transgender", "event", "specific"}),
            (
                "transgender event poetry reading trans lives matter stories poetry "
                "safe place self expression empowering identities pride flags"
            ),
            "transgender_poetry_event_bridge",
        ),
    (
            frozenset({"transgender", "event", "specific"}),
            (
                "transgender conference supportive professionals advocacy learn "
                "workshop accepted connected"
            ),
            "transgender_conference_event_bridge",
        ),
    (
            frozenset({"transgender", "event", "specific"}),
            (
                "transgender youth center talent show kids stage band colorful "
                "lights microphone music performance volunteer community"
            ),
            "transgender_youth_center_event_bridge",
        ),
    (
            frozenset({"book", "suggestion"}),
            _terms._BOOK_SUGGESTION_EXPANSION,
            "book_suggestion_bridge",
        ),
    (
            frozenset({"lewis"}),
            (
                "books author C S Lewis Narnia Chronicles wardrobe fantasy "
                "magical world Harry Potter universe characters spells magical creatures "
                "wizarding world Potter places London tour movie explore fan friend "
                "project getting lost magical world loves books"
            ),
            "book_suggestion_bridge",
        ),
    (
            frozenset({"book", "read"}),
            (
                "books read collection bookshelf Harry Potter Game of Thrones Name "
                "of the Wind Alchemist Hobbit Dance with Dragons Wheel of Time fantasy "
                "novel series finished favorite love"
            ),
            "book_reading_list_bridge",
        ),
    (
            frozenset({"book", "suggest"}),
            _terms._BOOK_SUGGESTION_EXPANSION,
            "book_suggestion_bridge",
        ),
    (
            frozenset({"book", "recommend"}),
            _terms._BOOK_SUGGESTION_EXPANSION,
            "book_suggestion_bridge",
        ),
    (
            frozenset({"book", "recommendation"}),
            _terms._BOOK_SUGGESTION_EXPANSION,
            "book_suggestion_bridge",
        ),
    (
            frozenset({"recommendation", "follow"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"suggestion", "follow"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"advice", "follow"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"recommendation", "make"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"suggestion", "make"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"what", "recommend"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"what", "suggest"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"recommendation", "read"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"suggestion", "read"}),
            _terms._RECOMMENDATION_SOURCE_EXPANSION,
            "recommendation_source_bridge",
        ),
    (
            frozenset({"children", "many"}),
            (
                "children kids brother siblings two younger kids son daughter scared "
                "reassured tough family"
            ),
            "children_count_sibling_bridge",
        ),
    (
            frozenset({"children", "many"}),
            "son accident roadtrip lucky okay ok scary car",
            "children_count_event_bridge",
        ),
    (
            frozenset({"attribute", "describe"}),
            (
                "attributes describe traits family rock thankful volunteering food "
                "supplies toy drive calm assistance rescue mission burning building "
                "purpose make difference helpful brave"
            ),
            "attribute_description_bridge",
        ),
    (
            frozenset({"attribute", "describe"}),
            (
                "attributes describe family rock tough times cheer love thankful "
                "family time centered support strength motivation grounded"
            ),
            "attribute_family_support_bridge",
        ),
    (
            frozenset({"attribute", "describe"}),
            (
                "attributes describe stayed calm asked assistance handled situation "
                "made it back safely resilience resourcefulness"
            ),
            "attribute_calm_resourcefulness_bridge",
        ),
    (
            frozenset({"attribute", "describe"}),
            (
                "attributes describe volunteer volunteering homeless shelter food "
                "supplies toy drive kids need community made difference helpful"
            ),
            "attribute_service_helpfulness_bridge",
        ),
    (
            frozenset({"attribute", "describe"}),
            (
                "attributes describe rescue mission firefighting brigade burning "
                "building pulled together energy purpose made difference brave "
                "community safe fulfilling meaningful"
            ),
            "attribute_rescue_purpose_bridge",
        ),
    (
            frozenset({"attribute", "describe"}),
            (
                "attributes describe traits selfless family-oriented passionate "
                "rational dedicated public service veterans education infrastructure "
                "policy tradeoffs support"
            ),
            "attribute_trait_inventory_bridge",
        ),
    (
            frozenset({"personality", "traits"}),
            (
                "thoughtful authentic driven drive determined dedicated passionate "
                "real care concern help helpful kind plan pitch awesome"
            ),
            "personality_trait_bridge",
        ),
    (
            frozenset({"personality", "traits"}),
            "thoughtful concern caring considerate precaution sign",
            "personality_thoughtfulness_bridge",
        ),
    (
            frozenset({"personality", "traits"}),
            "authentic real genuine true self care helping others",
            "personality_authenticity_bridge",
        ),
    (
            frozenset({"personality", "traits"}),
            "driven drive determined dedicated passionate plan pitch help awesome",
            "personality_drive_bridge",
        ),
    (
            frozenset({"reliable"}),
            (
                "behavior evidence reliable dependable responsible trustworthy kept "
                "promises followed through prepared consistently"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"responsible"}),
            (
                "behavior evidence reliable dependable responsible trustworthy kept "
                "promises followed through prepared consistently"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"trustworthy"}),
            (
                "behavior evidence reliable dependable responsible trustworthy kept "
                "promises followed through prepared consistently"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"dependable"}),
            (
                "behavior evidence reliable dependable responsible trustworthy kept "
                "promises followed through prepared consistently"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"organized"}),
            (
                "behavior evidence organized planned prepared scheduled coordinated "
                "managed followed through"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"creative"}),
            (
                "behavior evidence creative artistic designed created painted wrote "
                "made art project"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"helpful"}),
            (
                "behavior evidence helpful supportive caring listened helped offered "
                "comforted reassured encouraged patient thoughtful considerate"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"supportive"}),
            (
                "behavior evidence helpful supportive caring listened helped offered "
                "comforted reassured encouraged patient thoughtful considerate"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"caring"}),
            (
                "behavior evidence helpful supportive caring listened helped offered "
                "comforted reassured encouraged patient thoughtful considerate"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"patient"}),
            (
                "behavior evidence helpful supportive caring listened helped offered "
                "comforted reassured encouraged patient thoughtful considerate"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"thoughtful"}),
            (
                "behavior evidence helpful supportive caring listened helped offered "
                "comforted reassured encouraged patient thoughtful considerate"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"considerate"}),
            (
                "behavior evidence helpful supportive caring listened helped offered "
                "comforted reassured encouraged patient thoughtful considerate"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"disciplined"}),
            (
                "behavior evidence disciplined hardworking dedicated practiced trained "
                "worked consistently regularly completed finished focused prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"hardworking"}),
            (
                "behavior evidence disciplined hardworking dedicated practiced trained "
                "worked consistently regularly completed finished focused prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"dedicated"}),
            (
                "behavior evidence disciplined hardworking dedicated practiced trained "
                "worked consistently regularly completed finished focused prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"persistent"}),
            (
                "behavior evidence disciplined hardworking dedicated practiced trained "
                "worked consistently regularly completed finished focused prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"careful"}),
            (
                "behavior evidence careful thorough meticulous cautious checked "
                "verified reviewed detail carefully prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"thorough"}),
            (
                "behavior evidence careful thorough meticulous cautious checked "
                "verified reviewed detail carefully prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"meticulous"}),
            (
                "behavior evidence careful thorough meticulous cautious checked "
                "verified reviewed detail carefully prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"cautious"}),
            (
                "behavior evidence careful thorough meticulous cautious checked "
                "verified reviewed detail carefully prepared"
            ),
            "generic_behavior_inference_bridge",
        ),
    (
            frozenset({"roadtrip"}),
            "roadtrip accident scary scared bad start freaked lucky okay family",
            "adverse_trip_bridge",
        ),
    (
            frozenset({"song"}),
            _terms._CLASSICAL_MUSIC_PREFERENCE_EXPANSION,
            "classical_music_preference_bridge",
        ),
    (
            frozenset({"music"}),
            _terms._CLASSICAL_MUSIC_PREFERENCE_EXPANSION,
            "classical_music_preference_bridge",
        ),
    (
            frozenset({"vivaldi"}),
            _terms._CLASSICAL_MUSIC_PREFERENCE_EXPANSION,
            "classical_music_preference_bridge",
        ),
    (
            frozenset({"four", "seasons"}),
            _terms._CLASSICAL_MUSIC_PREFERENCE_EXPANSION,
            "classical_music_preference_bridge",
        ),
    (
            frozenset({"outdoor", "gear"}),
            (
                "outdoor gear company endorsement deal renowned Under Armour Nike "
                "Gatorade signed up sponsorship working with them cool"
            ),
            "endorsement_gear_brand_bridge",
        ),
    (
            frozenset({"screenshot"}),
            "ocr detected text written label title screen image visual текст написано",
            "visual_text_evidence_bridge",
        ),
    (
            frozenset({"image"}),
            "ocr detected text written label title photo picture visual текст написано",
            "visual_text_evidence_bridge",
        ),
    (
            frozenset({"audio"}),
            "transcript speech voice said told mentioned discussed audio транскрипт сказал сказала",
            "audio_transcript_evidence_bridge",
        ),
    (
            frozenset({"video"}),
            (
                "transcript speech said told mentioned discussed keyframe frame video audio "
                "транскрипт сказал сказала обсудили кадр"
            ),
            "video_transcript_evidence_bridge",
        ),
    (
            frozenset({"said", "about"}),
            _terms._SPEAKER_TURN_EXPANSION,
            "speaker_turn_bridge",
        ),
    (
            frozenset({"said", "про"}),
            _terms._SPEAKER_TURN_EXPANSION,
            "speaker_turn_bridge",
        ),
    (
            frozenset({"according"}),
            _terms._SPEAKER_TURN_EXPANSION,
            "speaker_turn_bridge",
        ),
    (
            frozenset({"perspective"}),
            _terms._SPEAKER_TURN_EXPANSION,
            "speaker_turn_bridge",
        ),
    (
            frozenset({"opinion"}),
            _terms._SPEAKER_TURN_EXPANSION,
            "speaker_turn_bridge",
        ),
    (
            frozenset({"словам"}),
            _terms._SPEAKER_TURN_EXPANSION,
            "speaker_turn_bridge",
        ),
    (
            frozenset({"call"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"talk"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"meet"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"chat"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"conversation"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"message"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"dm"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"spoke"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"talked"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"chatted"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"discussed"}),
            _terms._CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"созвон"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписка"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписке"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписки"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"перепиской"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписку"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписывался"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписывалась"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"переписывались"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"общался"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
    (
            frozenset({"говорил"}),
            _terms._RU_CONVERSATION_TRANSCRIPT_EXPANSION,
            "conversation_transcript_evidence_bridge",
        ),
)
