"""The personas the client already works with.

These four came from the product's mock data, where every field was written by
hand. The names, motivations, priorities and behaviours are kept exactly as they
were - they are the client's own segmentation and ours to match, not to invent.
What is new is `definition`: the motivations, priorities and behaviours written
as prose, because that is the text that gets embedded, and a comma-separated
list of nouns embeds to a worse centroid than a sentence does.

Nothing here is a measurement. A seed is a hypothesis about a segment; what the
corpus says about it is measured in build.py and stored separately, so the two
can never be confused for each other.
"""

SEEDS = [
    {
        "persona_id": "health-conscious",
        "name": "Health Conscious Consumer",
        "tagline": "Reads every label, optimizes for wellbeing",
        "motivations": ["Long-term wellbeing", "Clean ingredients", "Preventive health"],
        "priorities": ["Low sugar", "High protein", "Natural sourcing"],
        "behaviors": ["Compares nutrition panels", "Follows wellness creators",
                      "Buys functional dairy"],
        "definition": (
            "Eating for long-term wellbeing and preventive health. Cares about clean "
            "ingredients, low sugar, high protein and natural sourcing. Reads nutrition "
            "labels and compares them, follows wellness and nutrition creators, chooses "
            "functional and fortified foods. Talks about healthy eating, balanced diets, "
            "wholesome home cooking, gut health and what is actually in the product."
        ),
    },
    {
        "persona_id": "busy-family",
        "name": "Busy Family",
        "tagline": "Feeds the household, values trust and value",
        "motivations": ["Family nutrition", "Value for money", "Convenience"],
        "priorities": ["Trusted brands", "Kid-friendly", "Bulk value"],
        "behaviors": ["Shops weekly staples", "Watches promotions",
                      "Sticks to familiar brands"],
        "definition": (
            "Feeding a household on a budget and on a schedule. Cares about family "
            "nutrition, value for money and convenience. Buys trusted familiar brands, "
            "kid-friendly food and bulk value packs, shops weekly staples and watches "
            "for promotions. Talks about family meals, cooking for children, school "
            "lunchboxes, quick weeknight dinners, sharing food at home and feeding "
            "guests."
        ),
    },
    {
        "persona_id": "food-explorer",
        "name": "Food Explorer",
        "tagline": "Chases novelty, discovers via creators",
        "motivations": ["Novelty", "Discovery", "Shareability"],
        "priorities": ["New formats", "Aesthetics", "Limited editions"],
        "behaviors": ["Tries new launches", "Shares finds", "Follows food creators"],
        "definition": (
            "Chasing whatever is new and worth sharing. Motivated by novelty, discovery "
            "and shareability, drawn to new formats, striking aesthetics and limited "
            "editions. Tries new launches and new restaurants, photographs and shares "
            "what they find, follows food creators and viral recipes. Talks about trying "
            "somewhere for the first time, must-try dishes, viral food, new flavours and "
            "how something looks."
        ),
    },
    {
        "persona_id": "fitness-focused",
        "name": "Fitness Focused Consumer",
        "tagline": "Performance-driven, tracks every macro",
        "motivations": ["Performance", "Recovery", "Muscle gain"],
        "priorities": ["High protein", "Low sugar", "Functional"],
        "behaviors": ["Tracks macros", "Post-workout nutrition", "Follows athletes"],
        "definition": (
            "Eating for training performance and recovery. Motivated by muscle gain, "
            "strength and recovery, prioritises high protein, low sugar and functional "
            "products. Counts macros and calories, plans post-workout nutrition, meal "
            "preps, drinks protein shakes and follows athletes and coaches. Talks about "
            "protein intake, gym nutrition, calorie-controlled meals, supplements and "
            "body composition."
        ),
    },
]
