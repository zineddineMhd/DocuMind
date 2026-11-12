# Guide pratique du RAG (Retrieval-Augmented Generation)

## Qu'est-ce que le RAG ?

Le RAG, ou génération augmentée par la recherche, est une architecture qui combine un moteur de recherche documentaire et un grand modèle de langage (LLM). Au lieu de s'appuyer uniquement sur les connaissances mémorisées pendant son entraînement, le modèle reçoit dans son prompt des passages extraits d'une base documentaire, puis rédige sa réponse à partir de ces passages. Le terme a été introduit en 2020 par une équipe de Facebook AI Research dirigée par Patrick Lewis.

## Les avantages du RAG

Le RAG offre quatre avantages principaux. Il produit des réponses plus fiables et factuelles, car elles s'appuient sur des sources réelles. Il réduit les hallucinations des modèles de langage, c'est-à-dire les affirmations inventées. Il permet de mettre à jour les connaissances sans réentraîner le modèle : il suffit d'indexer de nouveaux documents. Enfin, il rend les réponses vérifiables grâce à la citation des sources utilisées.

## Le pipeline d'indexation

L'indexation se déroule en quatre étapes. Le texte est d'abord extrait des fichiers (PDF, DOCX, texte brut). Il est ensuite découpé en fragments appelés chunks, généralement de 500 à 1 000 caractères, avec un recouvrement de 10 à 20 % entre fragments consécutifs afin de ne pas couper une idée en deux. Chaque chunk est alors transformé en vecteur numérique par un modèle d'embeddings. Enfin, les vecteurs sont stockés dans une base vectorielle telle que ChromaDB, FAISS ou Qdrant, accompagnés de métadonnées comme le nom du document et le numéro de page.

## Le pipeline d'interrogation

Lorsqu'un utilisateur pose une question, celle-ci est convertie en vecteur avec le même modèle d'embeddings que celui utilisé à l'indexation. La base vectorielle renvoie les k chunks les plus proches, la proximité étant le plus souvent mesurée par la similarité cosinus. Une valeur de k comprise entre 5 et 8 constitue un bon point de départ. Les passages retrouvés sont insérés dans le prompt et le LLM rédige une réponse en citant ses sources.

## Recherche hybride et reranking

La recherche vectorielle retrouve les formulations équivalentes mais peut manquer des termes exacts comme une référence produit ou un acronyme. La recherche lexicale BM25 a le comportement inverse. La recherche hybride combine les deux listes de résultats, par exemple avec la fusion de rangs réciproques (Reciprocal Rank Fusion, RRF). Un reranker, typiquement un modèle cross-encoder, peut ensuite réordonner les candidats en lisant conjointement la question et chaque passage ; il est plus précis mais plus lent.

## Évaluer un système RAG

On évalue séparément la recherche et la génération. Pour la recherche, on mesure le Recall@k, c'est-à-dire la proportion de questions pour lesquelles le passage attendu figure parmi les k premiers résultats, ainsi que le MRR (Mean Reciprocal Rank). Pour la génération, on mesure la fidélité de la réponse aux sources, la validité des citations et le taux d'abstention approprié lorsque la réponse ne figure pas dans le corpus. Un jeu de 30 à 50 questions annotées suffit pour démarrer.

## Limites et risques

Un système RAG reste exposé à plusieurs risques. Le LLM peut halluciner malgré la présence de sources. Un document peut contenir une injection de prompt, c'est-à-dire un texte cherchant à détourner les instructions du modèle ; le contenu des documents doit donc toujours être traité comme une donnée non fiable. Enfin, un découpage inadapté ou un modèle d'embeddings mal choisi dégrade fortement la qualité de la recherche.
