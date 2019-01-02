"""Is create turing complete?"""
import re

import markovify

from ircbot import db

final_model = None


def register(bot):
    bot.listen(r'turing', markov, flags=re.IGNORECASE, require_mention=True)
    bot.listen(r'^!genmodels', build_models)

    build_models(bot)


def markov(bot, msg):
    """Return the best quote ever"""
    if final_model:
        output = final_model.make_sentence(tries=200)
        if output:
            # Put a zero width space in every word to prevent pings
            # This is also much simpler than using crazy IRC nick regex.
            # Put it in the middle of the word since nicks are quoted
            # using "<@keur>" syntax.
            msg.respond(
                ' '.join([w[:len(w) // 2] + '\u2060' + w[len(w) // 2:] for w in output.split()]),
                ping=False,
            )
        else:
            # This has never happened, but just in case...
            msg.respond(
                'Could not generate sentence. Please try again or run !genmodels',
                ping=False,
            )


def build_models(bot, msg=None):
    """Rebuild the markov models"""
    with db.cursor(password=bot.mysql_password) as c:
        # Fetch quote data
        c.execute('SELECT quote from quotes WHERE is_deleted = 0')
        quotes = c.fetchall()

        # Fetch inspire data
        c.execute('SELECT text from inspire')
        inspirations = c.fetchall()

        # Fetch iconic FOSS rants
        c.execute('SELECT text from rants')
        rants = c.fetchall()

    # Normalize the quote data... Get rid of IRC junk
    clean_quotes = [normalize_quote(d['quote']) for d in quotes]

    # Normalize the inspire data... Just lightly prune authors
    clean_inspirations = [normalize_inspiration(d['text']) for d in inspirations]

    # Normalize the rant data... just remove ending punctuation
    clean_rants = [normalize_rant(d['text']) for d in rants]

    # Create the three models, and combine them.
    # More heavily weight our quotes and rants
    global final_model
    rants_model = markovify.NewlineText('\n'.join(clean_rants))
    quotes_model = markovify.NewlineText('\n'.join(clean_quotes))
    inspire_model = markovify.NewlineText('\n'.join(clean_inspirations))
    final_model = markovify.combine([quotes_model, rants_model, inspire_model], [2, 2, 0.5])


def normalize_quote(q):
    # Remove timestamps
    cleaned = re.sub(r'\[?\d{2}:\d{2}(:?:\d{2})?\]?', '', q)
    # Remove "\\" newline separators
    cleaned = re.sub(r'\\\s*', '', cleaned)
    # Trim punctuation from end of quotes
    cleaned = re.sub(r'(\.|\?|!)$', '', cleaned)
    return cleaned


def normalize_inspiration(q):
    # Remove fancy en dash or double dash that start author clause
    cleaned = re.sub('—.*$', '', q)
    cleaned = re.sub('--.*$', '', cleaned)
    # Remove "\\" newline separators
    cleaned = re.sub(r'\\\s', '', cleaned)
    return cleaned.strip()


def normalize_rant(r):
    # Remove sentence ends because we need the newline model
    # so this will match up with our other datasets
    cleaned = re.sub(r'(\.|\?|!)$', '', r)
    return cleaned.strip()
