"""Optional Chroma-backed memory with a deterministic in-memory fallback."""

from typing import Any


class VectorMemory:
	"""Store business intents and report summaries using Chroma when available."""

	def __init__(self, persist_directory: str | None = None) -> None:
		self.backend = "memory"
		self._intents: list[dict[str, Any]] = []
		self._reports: list[dict[str, Any]] = []
		self._collections: dict[str, Any] = {}
		try:
			import chromadb
			client = chromadb.PersistentClient(path=persist_directory) if persist_directory else chromadb.Client()
			self._collections = {
				"intents": client.get_or_create_collection("business_intents"),
				"reports": client.get_or_create_collection("reports"),
			}
			self.backend = "chroma"
		except Exception:
			self._collections = {}

	def _store(self, collection: str, text: str, metadata: dict[str, Any] | None) -> None:
		record = {"text": text, "metadata": metadata or {}}
		if self.backend == "chroma":
			target = self._collections[collection]
			target.add(documents=[text], metadatas=[record["metadata"]], ids=[f"{collection}-{target.count()}"])
		else:
			(self._intents if collection == "intents" else self._reports).append(record)

	def store_intent(self, text: str, metadata: dict[str, Any] | None = None) -> None:
		"""Store a business intent."""
		self._store("intents", text, metadata)

	def store_report(self, text: str, metadata: dict[str, Any] | None = None) -> None:
		"""Store a report summary."""
		self._store("reports", text, metadata)

	def _retrieve(self, collection: str, query: str, limit: int) -> list[dict[str, Any]]:
		if self.backend == "chroma":
			result = self._collections[collection].query(query_texts=[query], n_results=limit)
			return [{"text": text, "metadata": metadata} for text, metadata in zip(result["documents"][0], result["metadatas"][0])]
		records = self._intents if collection == "intents" else self._reports
		words = set(query.lower().split())
		ranked = sorted(records, key=lambda item: len(words & set(item["text"].lower().split())), reverse=True)
		return ranked[:limit]

	def retrieve_similar_intents(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
		"""Retrieve intent records most similar to a query."""
		return self._retrieve("intents", query, limit)

	def retrieve_similar_reports(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
		"""Retrieve report records most similar to a query."""
		return self._retrieve("reports", query, limit)
