# -*- coding: utf-8 -*-
#
# Tuxemon
# Copyright (C) 2014, William Edwards <shadowapex@gmail.com>,
#                     Benjamin Bean <superman2k5@gmail.com>
#
# This file is part of Tuxemon.
#
# Tuxemon is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Tuxemon is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Tuxemon.  If not, see <http://www.gnu.org/licenses/>.
#
# Contributor(s):
#
# William Edwards <shadowapex@gmail.com>
# Leif Theden <leif.theden@gmail.com>
#
#
#
#
import logging
import os
import random
from collections import namedtuple

from tuxemon.core import prepare
from tuxemon.core.components import db
from tuxemon.core.components.locale import translator

logger = logging.getLogger(__name__)

trans = translator.translate

# Load the technique database
techniques = db.JSONDatabase()
techniques.load("technique")

tech_ret_value = namedtuple("use", "name success properties")

type_chart = namedtuple("TypeChart", ["strong_attack", "weak_attack", "extra_damage", "resist_damage"])

TYPES = {
    "aether": type_chart(None, None, None, None),
    "normal": type_chart(None, None, None, None),
    "wood": type_chart(
        "earth", "fire", "metal", "water"
    ),
    "fire": type_chart(
        "metal", "earth", "water", "wood"
    ),
    "earth": type_chart(
        "water", "metal", "wood", "fire"
    ),
    "metal": type_chart(
        "wood", "water", "fire", "earth"
    ),
    "water": type_chart(
        "fire", "wood", "earth", "metal"
    ),
}


def merge_results(result, meta_result):
    status = result.pop("status", None)
    if status:
        meta_result["statuses"].append(status)
    meta_result.update(result)
    return meta_result


class Technique(object):
    """A technique object is a particular skill that tuxemon monsters can use
    in battle.

    **Example:**

    >>> poison_tech = Technique("technique_poison_sting")
    >>> pprint.pprint(poison_tech.__dict__)
        {'category': u'special',
         'effect': [u'poison', u'damage'],
         'name': u'Poison Sting',
         'power': 40,
         'tech_id': 2,
         'type1': u'Poison',
         'type2': None}

    """

    def __init__(self, slug=None, carrier=None, link=None):
        self._combat_counter = 0  # number of turns that this technique has been active
        self.accuracy = 0
        self.animation = None
        self.can_apply_status = False
        self.carrier = carrier
        self.category = "attack"
        self.effect = []
        self.images = []
        self.is_area = False
        self.is_fast = False
        self.link = link
        self.name = "Pound"
        self.next_use = 0
        self.potency = 0
        self.power = 1
        self.range = None
        self.recharge_length = 0
        self.slug = slug
        self.type1 = "aether"
        self.type2 = None

        # If a slug of the technique was provided, autoload it.
        if slug:
            self.load(slug)

    def load(self, slug):
        """Loads and sets this technique's attributes from the technique
        database. The technique is looked up in the database by slug.

        :param slug: The slug of the technique to look up in the database.

        :type slug: String

        :rtype: None
        :returns: None

        **Examples:**

        >>>

        """

        results = techniques.lookup(slug, table="technique")
        self.slug = results["slug"]  # a short English identifier
        self.name = trans(results["name_trans"])  # locale-specific string

        self.sort = results['sort']

        # must be translated before displaying
        self.execute_trans = results['execute_trans']
        self.success_trans = results['success_trans']
        self.failure_trans = results['failure_trans']

        self.category = results["category"]
        self.icon = results["icon"]
        self._combat_counter = 0
        self._life_counter = 0

        if results.get('types'):
            self.type1 = results["types"][0]
            if len(results['types']) > 1:
                self.type2 = results["types"][1]
            else:
                self.type2 = None
        else:
            self.type1 = self.type2 = None

        self.power = results.get("power")
        self.is_fast = results.get("is_fast")
        self.recharge_length = results.get("recharge")
        self.is_area = results.get("is_area")
        self.range = results.get("range")
        self.accuracy = results.get("accuracy")
        self.potency = results.get("potency")
        self.effect = results["effects"]
        self.target = db.process_targets(results["target"])

        # Load the animation sprites that will be used for this technique
        self.animation = results["animation"]
        if self.animation:
            self.images = []
            animation_dir = prepare.BASEDIR + prepare.DATADIR + "/animations/technique/"
            directory = sorted(os.listdir(animation_dir))
            for image in directory:
                if self.animation and image.startswith(self.animation):
                    self.images.append("animations/technique/" + image)

        # Load the sound effect for this technique
        sfx_directory = "sounds/technique/"
        self.sfx = sfx_directory + results["sfx"]

    def advance_round(self, number=1):
        """ Advance the turn counters for this technique

        Techniques have two counters currently, a "combat counter" and a "life counter".
        Combat counters should be reset with combat begins.
        Life counters will be set to zero when the Technique is created, but will never
        be reset.

        Calling this function will advance both counters

        :return: None
        """
        self._combat_counter += 1
        self._life_counter += 1

    def recharge(self):
        self.next_use -= 1

    def full_recharge(self):
        self.next_use = 0

    def reset_combat_counter(self):
        """ Reset the combat counter.
        """
        self._combat_counter = 0

    def use(self, user, target):
        """Applies this technique's effects as defined in the "effect" column of the technique
        database. This method will execute a function with the same name as the effect defined in
        the database. If you want to add a new effect, simply create a new function under the
        Technique class with the name of the effect you define in monster.db.

        :param user: The Monster object that used this technique.
        :param target: Monster object that we are using this technique on.

        :type user: core.components.monster.Monster
        :type target: core.components.monster.Monster

        :rtype: dictionary
        :returns: a dictionary with the effect name, success and misc properties

        **Examples:**

        >>> poison_tech = Technique("technique_poison_sting")
        >>> bulbatux.learn(poison_tech)
        >>>
        >>> bulbatux.moves[0].use(user=bulbatux, target=tuxmander)
        """
        # Loop through all the effects of this technique and execute the effect's function.
        # TODO: more robust API
        # TODO: separate classes for each Technique
        # TODO: consider moving message templates to the JSON DB

        # defaults for the return. items can override these values in their return.
        meta_result = {
            'name': self.name,
            'success': False,
            'should_tackle': False,
            'capture': False,
            'statuses': [],
        }

        # TODO: handle conflicting values from multiple technique actions
        # TODO: for example, how to handle one saying success, and another not?
        for effect in self.effect:
            if effect == "damage":
                result = self.damage(user, target)
            elif effect == "poison":
                result = self.apply_status("status_poison", target)
            elif effect == "lifeleech":
                result = self.apply_lifeleech(user, target)
            elif effect == "recover":
                result = self.apply_status("status_recover", user)
            elif effect == "status":
                if self.category == "poison":
                    result = self.poison(target)
                elif self.category == "lifeleech":
                    result = self.lifeleech(target)
                elif self.category == "recover":
                    result = self.recover(target)
                else:
                    result = getattr(self, self.category)(target)
            else:
                result = getattr(self, str(effect))(user, target)
            meta_result = merge_results(result, meta_result)

        self.next_use = self.recharge_length

        return meta_result

    def calculate_damage(self, user, target):
        """ Calc. damage for the damage technique

        :param user: The Monster object that used this technique.
        :param target: The Monster object that we are using this technique on.

        :type user: core.components.monster.Monster
        :type target: core.components.monster.Monster

        :rtype: tuple(int, str)
        """
        if self.range == "melee":
            user_strength = user.melee * (7 + user.level)
            target_resist = target.armour
        elif self.range == "touch":
            user_strength = user.melee * (7 + user.level)
            target_resist = target.dodge
        elif self.range == "ranged":
            user_strength = user.ranged * (7 + user.level)
            target_resist = target.dodge
        elif self.range == "reach":
            user_strength = user.ranged * (7 + user.level)
            target_resist = target.armour
        elif self.range == "reliable":
            user_strength = 7 + user.level
            target_resist = 1
        else:
            logger.error('unhandled damage category %s %s', self.category, self.range)
            raise RuntimeError

        mult = self.get_damage_multiplier(target)
        move_strength = self.power * mult
        damage = int(user_strength * move_strength / target_resist)
        return damage, mult

    def damage(self, user, target):
        """ This effect applies damage to a target monster. Damage calculations are based upon the
        original Pokemon battle damage formula. This effect will be applied if "damage" is defined
        in this technique's effect list.

        :param user: The Monster object that used this technique.
        :param target: The Monster object that we are using this technique on.

        :type user: core.components.monster.Monster
        :type target: core.components.monster.Monster

        :rtype: dict
        """
        hit = self.accuracy >= random.random()
        if hit or self.is_area:
            self.can_apply_status = True
            damage, mult = self.calculate_damage(user, target)
            if not hit:
                damage /= 2
            target.current_hp -= damage
        else:
            damage = 0
            mult = 1

        return {
            'damage': damage,
            'element_multiplier': mult,
            'should_tackle': bool(damage),
            'success': bool(damage),
        }

    def apply_status(self, slug, target):
        """ This effect has a chance to apply a status effect to a target monster.

        :param target: The Monster object that we are using this technique on.
        :param slug: The Monster object that we are using this technique on.

        :type user: core.components.monster.Monster
        :type target: core.components.monster.Monster

        :rtype: dict
        """
        already_applied = any(t for t in target.status if t.slug == slug)
        success = not already_applied and self.can_apply_status and self.potency >= random.random()
        tech = None
        if success:
            tech = Technique(slug, carrier=target)
            target.apply_status(tech)

        return {
            'status': tech,
        }

    def apply_lifeleech(self, user, target):
        """ This effect has a chance to apply the lifeleech status effect to a target monster.

        :param user: The Monster object that used this technique.
        :param target: The Monster object that we are using this technique on.

        :type user: core.components.monster.Monster
        :type target: core.components.monster.Monster

        :rtype: dict
        """
        already_applied = any(t for t in target.status if t.slug == "status_lifeleech")
        success = not already_applied and self.can_apply_status and self.potency >= random.random()
        tech = None
        if success:
            tech = Technique("status_lifeleech", carrier=target, link=user)
            target.apply_status(tech)

        return {
            'status': tech,
        }

    def poison(self, target):
        damage = target.hp / 8
        target.current_hp -= damage
        return {
            'damage': damage,
            'should_tackle': bool(damage),
            'success': bool(damage),
        }

    def recover(self, target):
        heal = min(target.hp / 16, target.hp - target.current_hp)
        target.current_hp += heal
        return {
            'damage': heal,
            'should_tackle': False,
            'success': bool(heal),
        }

    def lifeleech(self, target):
        user = self.link
        damage = min(target.hp / 2, target.current_hp, user.hp - user.current_hp)
        target.current_hp -= damage
        user.current_hp += damage
        return {
            'damage': damage,
            'should_tackle': bool(damage),
            'success': bool(damage),
        }

    def faint(self, user, target):
        """ Faint this monster.  Typically, called by combat to faint self, not others.

        :param user: The Monster object that used this technique.
        :param target: The Monster object that we are using this technique on.

        :type user: core.components.monster.Monster
        :type target: core.components.monster.Monster

        :rtype: dict
        """
        # TODO: implement into the combat state, currently not used

        already_fainted = any(t for t in target.status if t.name == "status_faint")

        if already_fainted:
            raise RuntimeError

        target.apply_status(Technique("status_faint"))

        return {
            'should_tackle': False,
            'success': True,
        }

    def swap(self, user, target):
        """ Used just for combat: change order of monsters

        Position of monster in party will be changed

        :param user: core.components.monster.Monster
        :param target: core.components.monster.Monster

        :rtype: dict
        """
        # TODO: implement actions as events, so that combat state can find them
        # TODO: relies on setting "combat_state" attribute.  maybe clear it up later
        # TODO: these values are set in combat_menus.py

        def swap_add():
            # TODO: make accommodations for battlefield positions
            combat_state.add_monster_into_play(user, target)

        # TODO: find a way to pass values. this will only work for SP games with one monster party
        combat_state = self.combat_state
        # get the original monster to be swapped out
        original_monster = combat_state.monsters_in_play[user][0]

        # rewrite actions to target the new monster.  must be done before original is removed
        combat_state.rewrite_action_queue_target(original_monster, target)

        # remove the old monster and all their actions
        combat_state.remove_monster_from_play(user, original_monster)

        # give a slight delay
        combat_state.task(swap_add, .75)
        combat_state.suppress_phase_change(.75)

        return {
            'success': True,
            'should_tackle': False,
        }

    def get_state(self):
        return self.slug

    def get_damage_multiplier(self, target):
        m = 1
        for attack_type in (self.type1, self.type2):
            if attack_type is None:
                continue
            for target_type in (target.type1, target.type2):
                body = TYPES.get(target_type, TYPES["aether"])
                if body.extra_damage is None:
                    continue
                if attack_type == body.extra_damage:
                    m *= 2
                elif attack_type == body.resist_damage:
                    m /= 2.0
        m = min(4, m)
        m = max(0.25, m)
        return m
